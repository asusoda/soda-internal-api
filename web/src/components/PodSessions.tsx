import { useCallback, useEffect, useState, type FormEvent } from "react";
import { toast } from "react-toastify";
import axios from "axios";
import apiClient from "./utils/axios";
import type { PodSession } from "../computeTypes";
import type { ApiError } from "../types";

const input = "p-1.5 rounded bg-gray-800 border border-gray-700 text-white text-sm";
const button = "px-3 py-1.5 rounded text-sm border border-gray-600 text-gray-200 hover:bg-gray-700 disabled:opacity-50";

const errorText = (error: unknown, fallback: string) =>
  (axios.isAxiosError<ApiError>(error) && error.response?.data?.error) || fallback;

interface PodSessionsProps {
  orgPrefix: string;
  podId: string;
}

// Times the pod runs. The server starts it 10 minutes before each session and stops it after.
const PodSessions = ({ orgPrefix, podId }: PodSessionsProps) => {
  const [sessions, setSessions] = useState<PodSession[]>([]);
  const [form, setForm] = useState({ title: "", start: "", stop: "" });
  const base = `/api/compute/${orgPrefix}/pods/${podId}/sessions`;

  const load = useCallback(async () => {
    try {
      const response = await apiClient.get<{ sessions: PodSession[] }>(base);
      setSessions(response.data.sessions || []);
    } catch (error) {
      toast.error(errorText(error, "Could not load sessions"));
    }
  }, [base]);

  useEffect(() => {
    load();
  }, [load]);

  const add = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      await apiClient.post(base, {
        title: form.title || null,
        start_at: new Date(form.start).toISOString(),
        stop_at: new Date(form.stop).toISOString(),
      });
      setForm({ title: "", start: "", stop: "" });
      await load();
    } catch (error) {
      toast.error(errorText(error, "Could not add the session"));
    }
  };

  const remove = async (session: PodSession) => {
    try {
      await apiClient.delete(`${base}/${session.id}`);
      await load();
    } catch (error) {
      toast.error(errorText(error, "Could not remove the session"));
    }
  };

  const upcoming = sessions.filter((s) => !s.finished);

  return (
    <div className="p-3 bg-gray-900/50 rounded">
      <p className="text-gray-400 text-xs mb-2">
        The pod starts 10 minutes before each session and stops when the last one ends.
      </p>
      {upcoming.length === 0 && <p className="text-gray-500 text-sm mb-2">No upcoming sessions.</p>}
      {upcoming.map((session) => (
        <div key={session.id} className="flex items-center justify-between text-sm text-gray-300 mb-1">
          <span>
            {session.title ? `${session.title}: ` : ""}
            {new Date(session.start_at).toLocaleString()} to {new Date(session.stop_at).toLocaleString()}
          </span>
          <button className={button} onClick={() => remove(session)}>
            Remove
          </button>
        </div>
      ))}
      <form onSubmit={add} className="flex flex-wrap gap-2 mt-2">
        <input className={input} placeholder="Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
        <input className={input} type="datetime-local" required value={form.start} onChange={(e) => setForm({ ...form, start: e.target.value })} />
        <input className={input} type="datetime-local" required value={form.stop} onChange={(e) => setForm({ ...form, stop: e.target.value })} />
        <button className={button} type="submit">
          Add session
        </button>
      </form>
    </div>
  );
};

export default PodSessions;
