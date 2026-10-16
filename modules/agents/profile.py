"""The member's profile graph: facts as nodes and edges, nearest nodes by embedding, and deletes
of a member's agent data. No Flask here."""

import math
from typing import Any

from sqlalchemy import func, or_, text
from sqlalchemy.orm import aliased

from core import limits
from core.log import get_logger
from core.time import iso, utcnow
from modules.agents import service
from modules.agents.models import (
    AgentConversation,
    AgentMemory,
    AgentMessage,
    AgentPendingAction,
    AgentProfileEdge,
    AgentProfileNode,
)
from modules.agents.service import AgentError, Owner
from modules.knowledge.embedder import Embedder, EmbeddingError
from modules.knowledge.models import DIMENSIONS, Embedding, vector_sql

logger = get_logger("agents")


def _entity(value: Any, name: str) -> tuple[str, str]:
    if not isinstance(value, dict):
        raise AgentError(f"{name} must be an object with kind and label")
    return service.text(value.get("kind"), f"{name}.kind", 100), service.text(value.get("label"), f"{name}.label", 500)


def _node(db, who: Owner, kind: str, label: str, confidence: float) -> AgentProfileNode:
    node = (
        db.query(AgentProfileNode)
        .filter_by(organization_id=who.organization_id, discord_id=who.discord_id, kind=kind, label=label)
        .first()
    )
    if node is None:
        node = AgentProfileNode(
            organization_id=who.organization_id,
            discord_id=who.discord_id,
            kind=kind,
            label=label,
            confidence=confidence,
            agent_token_id=who.token_id,
        )
        db.add(node)
        db.flush()
    else:
        node.confidence = max(float(node.confidence), confidence)
        node.updated_at = utcnow()
    return node


def _embed_nodes(nodes: list[AgentProfileNode], embedder: Embedder) -> None:
    """Give nodes without a vector from this model one, from "kind: label".

    A failure, or an org over its embeddings limit, leaves them without.
    """
    todo = [n for n in nodes if n.embedding is None or n.embedding_model != embedder.model]
    if not todo:
        return
    try:
        vectors = embedder.embed([f"{n.kind}: {n.label}" for n in todo])
    except (EmbeddingError, limits.LimitError):
        logger.warning("profile nodes stored without embeddings count=%s", len(todo))
        return
    if any(len(v) != DIMENSIONS for v in vectors):
        logger.warning("embedding service returned vectors that are not %s long", DIMENSIONS)
        return
    for node, vector in zip(todo, vectors, strict=True):
        node.embedding, node.embedding_model = vector, embedder.model


def upsert(db, who: Owner, facts: Any, *, commit: bool = True, embedder: Embedder | None = None) -> int:
    """Store facts, each {"subject": {kind, label}, "relation", "object": {kind, label}, "confidence"}.

    Existing nodes and edges keep the higher confidence. With an embedder, nodes get vectors for
    similar(). One transaction. Returns how many facts.
    """
    if not isinstance(facts, list):
        raise AgentError("facts must be a list")
    parsed = []
    for fact in facts:
        if not isinstance(fact, dict):
            raise AgentError("each fact must be an object")
        parsed.append(
            (
                _entity(fact.get("subject"), "subject"),
                service.text(fact.get("relation"), "relation", 200),
                _entity(fact.get("object"), "object"),
                service.confidence(fact.get("confidence")),
            )
        )
    touched: dict[str, AgentProfileNode] = {}
    for (s_kind, s_label), relation, (o_kind, o_label), confidence in parsed:
        subject = _node(db, who, s_kind, s_label, confidence)
        obj = _node(db, who, o_kind, o_label, confidence)
        touched[str(subject.id)], touched[str(obj.id)] = subject, obj
        edge = db.query(AgentProfileEdge).filter_by(from_node=subject.id, to_node=obj.id, relation=relation).first()
        if edge is None:
            db.add(
                AgentProfileEdge(
                    organization_id=who.organization_id,
                    from_node=subject.id,
                    to_node=obj.id,
                    relation=relation,
                    confidence=confidence,
                )
            )
            db.flush()
        else:
            edge.confidence = max(float(edge.confidence), confidence)
    if embedder is not None:
        _embed_nodes(list(touched.values()), embedder)
    service.save(db, commit)
    return len(parsed)


def _node_dict(n: AgentProfileNode) -> dict:
    return {
        "id": n.id,
        "kind": n.kind,
        "label": n.label,
        "confidence": n.confidence,
        "created_at": iso(n.created_at),
        "updated_at": iso(n.updated_at),
    }


def profile_nodes(db, who: Owner, limit: object = None) -> list[dict]:
    rows = (
        db.query(AgentProfileNode)
        .filter_by(organization_id=who.organization_id, discord_id=who.discord_id)
        .order_by(AgentProfileNode.confidence.desc(), AgentProfileNode.updated_at.desc())
        .limit(service.limit(limit, 50))
        .all()
    )
    return [_node_dict(n) for n in rows]


def similar(db, who: Owner, query: object, limit: object, embedder: Embedder | None) -> list[dict]:
    """The member's profile nodes nearest to the text, nearest first, each with its cosine distance.

    Empty when the org is over its embeddings limit.
    """
    if embedder is None:
        raise AgentError("Similar nodes need an embeddings service. Set one on the Integrations page", 503)
    query_text = service.text(query, "text", 2000)
    count = service.limit(limit, 10)
    try:
        vector = embedder.embed_query(query_text)
    except EmbeddingError as e:
        raise AgentError("The embedding service failed", 502) from e
    except limits.LimitError:
        logger.warning("profile query not embedded, the org is over its embeddings limit")
        return []
    if vector_sql(db, "agent_profile_nodes"):
        params = {
            "org": who.organization_id,
            "member": who.discord_id,
            "model": embedder.model,
            "vec": Embedding().process_bind_param(vector, None),
            "n": count,
        }
        scored = [
            (float(distance), node_id)
            for node_id, distance in db.execute(
                text(
                    "SELECT id, embedding <=> CAST(:vec AS vector) AS distance FROM agent_profile_nodes"
                    " WHERE organization_id = :org AND discord_id = :member AND embedding IS NOT NULL"
                    " AND embedding_model = :model ORDER BY distance LIMIT :n"
                ),
                params,
            )
        ]
    else:
        rows = db.query(AgentProfileNode.id, AgentProfileNode.embedding).filter(
            AgentProfileNode.organization_id == who.organization_id,
            AgentProfileNode.discord_id == who.discord_id,
            AgentProfileNode.embedding.isnot(None),
            AgentProfileNode.embedding_model == embedder.model,
        )
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        scored = []
        for node_id, embedding in rows:
            other = math.sqrt(sum(x * x for x in embedding)) or 1.0
            scored.append((1.0 - sum(a * b for a, b in zip(vector, embedding, strict=False)) / (norm * other), node_id))
        scored = sorted(scored)[:count]
    nodes = {n.id: n for n in db.query(AgentProfileNode).filter(AgentProfileNode.id.in_([i for _, i in scored]))}
    return [{**_node_dict(nodes[i]), "distance": round(d, 6)} for d, i in scored if i in nodes]


def _relations_query(db, who: Owner):
    subject = aliased(AgentProfileNode)
    obj = aliased(AgentProfileNode)
    query = (
        db.query(AgentProfileEdge, subject, obj)
        .join(subject, subject.id == AgentProfileEdge.from_node)
        .join(obj, obj.id == AgentProfileEdge.to_node)
        .filter(
            AgentProfileEdge.organization_id == who.organization_id,
            subject.organization_id == who.organization_id,
            subject.discord_id == who.discord_id,
        )
    )
    return query, subject


def _relation_dict(edge: AgentProfileEdge, subject: AgentProfileNode, obj: AgentProfileNode) -> dict:
    return {
        "subject": {"kind": subject.kind, "label": subject.label},
        "relation": edge.relation,
        "object": {"kind": obj.kind, "label": obj.label},
        "confidence": edge.confidence,
    }


def relations(db, who: Owner, limit: object = None) -> list[dict]:
    query, _ = _relations_query(db, who)
    rows = (
        query.order_by(AgentProfileEdge.confidence.desc(), AgentProfileEdge.created_at.desc())
        .limit(service.limit(limit, 50))
        .all()
    )
    return [_relation_dict(*row) for row in rows]


def matching(db, who: Owner, subject_label: object, relation: object) -> list[dict]:
    """Relations from a subject label with a relation name, both compared without case."""
    label = service.text(subject_label, "subject", 500)
    name = service.text(relation, "relation", 200)
    query, subject = _relations_query(db, who)
    rows = (
        query.filter(func.lower(subject.label) == label.lower(), func.lower(AgentProfileEdge.relation) == name.lower())
        .order_by(AgentProfileEdge.created_at)
        .all()
    )
    return [_relation_dict(*row) for row in rows]


def drop_relation(db, who: Owner, subject_label: object, relation: object, object_label: object) -> bool:
    """Delete one edge, compared without case. Both nodes stay."""
    target = service.text(object_label, "object", 500).lower()
    query, subject = _relations_query(db, who)
    label = service.text(subject_label, "subject", 500)
    name = service.text(relation, "relation", 200)
    rows = query.filter(
        func.lower(subject.label) == label.lower(), func.lower(AgentProfileEdge.relation) == name.lower()
    ).all()
    edges = [edge for edge, _, obj in rows if str(obj.label).lower() == target]
    for edge in edges:
        db.delete(edge)
    db.commit()
    return bool(edges)


def _delete_nodes(db, nodes: list[AgentProfileNode]) -> int:
    ids = [n.id for n in nodes]
    if not ids:
        return 0
    db.query(AgentProfileEdge).filter(
        or_(AgentProfileEdge.from_node.in_(ids), AgentProfileEdge.to_node.in_(ids))
    ).delete(synchronize_session=False)
    db.query(AgentProfileNode).filter(AgentProfileNode.id.in_(ids)).delete(synchronize_session=False)
    return len(ids)


def forget(db, who: Owner, label: object) -> int:
    """Delete every node with this exact label and its edges. Returns nodes deleted. Commits."""
    exact = service.text(label, "label", 500)
    nodes = (
        db.query(AgentProfileNode)
        .filter_by(organization_id=who.organization_id, discord_id=who.discord_id, label=exact)
        .all()
    )
    count = _delete_nodes(db, nodes)
    db.commit()
    return count


def forget_all(db, who: Owner) -> int:
    """Delete the member's profile graph and memories. Conversations stay. Returns rows deleted. Commits."""
    nodes = db.query(AgentProfileNode).filter_by(organization_id=who.organization_id, discord_id=who.discord_id).all()
    count = _delete_nodes(db, nodes)
    count += db.query(AgentMemory).filter_by(organization_id=who.organization_id, discord_id=who.discord_id).delete()
    db.commit()
    return count


def forget_everything(db, who: Owner) -> int:
    """Delete every conversation, memory and profile row of the member. Returns rows deleted. Commits."""
    ids = [
        row.id
        for row in db.query(AgentConversation.id)
        .filter_by(organization_id=who.organization_id, discord_id=who.discord_id)
        .all()
    ]
    if ids:
        db.query(AgentMessage).filter(AgentMessage.conversation_id.in_(ids)).delete(synchronize_session=False)
        db.query(AgentConversation).filter(AgentConversation.id.in_(ids)).delete(synchronize_session=False)
    db.query(AgentPendingAction).filter_by(organization_id=who.organization_id, discord_id=who.discord_id).delete()
    return len(ids) + forget_all(db, who)
