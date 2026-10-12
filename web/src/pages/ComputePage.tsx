import React, { useCallback, useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import axios from "axios";
import { FaClock, FaFolderOpen, FaPlay, FaPlus, FaServer, FaStop, FaSync, FaTrash, FaUndo } from "react-icons/fa";
import { useAuth } from "../components/auth/AuthContext";
import OrganizationNavbar from "../components/shared/OrganizationNavbar";
import PodSessions from "../components/PodSessions";
import ThemedLoading from "../components/ui/ThemedLoading";
import apiClient from "../components/utils/axios";
import type { Pod, PodAction } from "../computeTypes";
import type { ApiError } from "../types";

const errorText = (error: unknown, fallback: string) =>
  (axios.isAxiosError<ApiError>(error) && error.response?.data?.error) || fallback;

// The values of the new pod form. A number input gives a string.
interface PodForm {
  name: string;
  gpu_type_id: string;
  use_cpu_only: boolean;
  cloud_type: string;
  volume_in_gb: number | string;
  container_disk_in_gb: number | string;
  is_public: boolean;
}

// The body of POST /pods. A CPU-only pod has no gpu_type_id.
type PodCreateBody = Omit<PodForm, "gpu_type_id" | "volume_in_gb" | "container_disk_in_gb"> & {
  gpu_type_id?: string;
  volume_in_gb: number;
  container_disk_in_gb: number;
};

// The fields of PUT /pods/<pod_id> that this page changes.
type PodShareChanges = Partial<Pick<Pod, "is_public" | "allowed_users">>;

const EMPTY_FORM: PodForm = {
  name: "",
  gpu_type_id: "NVIDIA RTX A4000",
  use_cpu_only: false,
  cloud_type: "COMMUNITY",
  volume_in_gb: 1,
  container_disk_in_gb: 2,
  is_public: false,
};

const input = "w-full p-2 rounded bg-gray-800 border border-gray-700 text-white text-sm";
const button = "px-3 py-1.5 rounded text-sm border border-gray-600 text-gray-200 hover:bg-gray-700 disabled:opacity-50";

const ComputePage = () => {
  const { currentOrg } = useAuth();
  const navigate = useNavigate();
  const [pods, setPods] = useState<Pod[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [showForm, setShowForm] = useState(false);
  const [openSessions, setOpenSessions] = useState<string | null>(null);
  const base = `/api/compute/${currentOrg?.prefix}/pods`;

  const load = useCallback(async () => {
    if (!currentOrg) return;
    try {
      setLoading(true);
      const response = await apiClient.get<{ pods: Pod[] }>(base);
      setPods(response.data.pods || []);
    } catch (error) {
      toast.error(errorText(error, "Could not load pods"));
    } finally {
      setLoading(false);
    }
  }, [base, currentOrg]);

  useEffect(() => {
    load();
  }, [load]);

  const create = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const body: PodCreateBody = { ...form, volume_in_gb: Number(form.volume_in_gb), container_disk_in_gb: Number(form.container_disk_in_gb) };
    if (body.use_cpu_only) delete body.gpu_type_id;
    try {
      setBusy("create");
      await apiClient.post(base, body);
      toast.success("Pod created");
      setForm(EMPTY_FORM);
      setShowForm(false);
      await load();
    } catch (error) {
      toast.error(errorText(error, "Could not create the pod"));
    } finally {
      setBusy(null);
    }
  };

  const act = async (pod: Pod, action: PodAction) => {
    if (action === "terminate" && !window.confirm(`Terminate ${pod.name}? Its disk is deleted.`)) return;
    try {
      setBusy(pod.id);
      await apiClient.post(`${base}/${pod.id}/action`, { action });
      await load();
    } catch (error) {
      toast.error(errorText(error, `Could not ${action} the pod`));
    } finally {
      setBusy(null);
    }
  };

  const share = async (pod: Pod, changes: PodShareChanges) => {
    try {
      setBusy(pod.id);
      await apiClient.put(`${base}/${pod.id}`, changes);
      await load();
    } catch (error) {
      toast.error(errorText(error, "Could not change who may connect"));
    } finally {
      setBusy(null);
    }
  };

  const editUsers = (pod: Pod) => {
    const answer = window.prompt("Discord ids allowed to connect, comma separated", pod.allowed_users.join(", "));
    if (answer === null) return;
    share(pod, { allowed_users: answer.split(",").map((id) => id.trim()).filter(Boolean) });
  };

  const field = <K extends keyof PodForm>(key: K) => ({
    value: form[key],
    onChange: (e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setForm({
        ...form,
        [key]: e.target instanceof HTMLInputElement && e.target.type === "checkbox" ? e.target.checked : e.target.value,
      }),
  });

  return (
    <OrganizationNavbar>
      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2 flex items-center">
              <FaServer className="mr-3" /> Compute
            </h1>
            <p className="text-gray-400">Pods on {currentOrg?.name}'s RunPod account. Members connect with SSH.</p>
          </div>
          <div className="flex gap-2">
            <button className={button} onClick={load} title="Refresh">
              <FaSync />
            </button>
            <button className={button} onClick={() => setShowForm(!showForm)}>
              <FaPlus className="inline mr-1" /> New pod
            </button>
          </div>
        </div>

        {showForm && (
          <form onSubmit={create} className="mb-6 p-4 rounded-lg border border-gray-700 bg-gray-900/50 grid grid-cols-2 gap-3">
            <label className="text-gray-300 text-sm">
              Name
              <input className={input} required {...field("name")} />
            </label>
            <label className="text-gray-300 text-sm">
              GPU type
              <input className={input} disabled={form.use_cpu_only} {...field("gpu_type_id")} />
            </label>
            <label className="text-gray-300 text-sm">
              Cloud
              <select className={input} {...field("cloud_type")}>
                <option value="COMMUNITY">Community</option>
                <option value="SECURE">Secure</option>
              </select>
            </label>
            <label className="text-gray-300 text-sm">
              Volume (GB)
              <input className={input} type="number" min="0" {...field("volume_in_gb")} />
            </label>
            <label className="text-gray-300 text-sm">
              Container disk (GB)
              <input className={input} type="number" min="1" {...field("container_disk_in_gb")} />
            </label>
            <div className="flex items-end gap-4 text-gray-300 text-sm">
              <label>
                <input type="checkbox" checked={form.use_cpu_only} onChange={field("use_cpu_only").onChange} /> CPU only
              </label>
              <label>
                <input type="checkbox" checked={form.is_public} onChange={field("is_public").onChange} /> Every member
              </label>
            </div>
            <div className="col-span-2">
              <button className={button} type="submit" disabled={busy === "create"}>
                Create
              </button>
            </div>
          </form>
        )}

        {loading ? (
          <ThemedLoading message="Loading pods..." />
        ) : pods.length === 0 ? (
          <p className="text-gray-400">No pods yet.</p>
        ) : (
          <table className="w-full text-sm text-left text-gray-300">
            <thead className="text-gray-400 border-b border-gray-700">
              <tr>
                <th className="py-2">Name</th>
                <th>Status</th>
                <th>Who may connect</th>
                <th>Cost/hr</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {pods.map((pod) => (
                <React.Fragment key={pod.id}>
                <tr className="border-b border-gray-800">
                  <td className="py-2">
                    <div className="text-white">{pod.name}</div>
                    <div className="text-xs text-gray-500">{pod.id}</div>
                  </td>
                  <td>{pod.status}</td>
                  <td>
                    <label className="mr-3">
                      <input
                        type="checkbox"
                        checked={pod.is_public}
                        disabled={busy === pod.id}
                        onChange={(e) => share(pod, { is_public: e.target.checked })}
                      />{" "}
                      Everyone
                    </label>
                    <button className="underline text-gray-400" onClick={() => editUsers(pod)}>
                      {pod.allowed_users.length} listed
                    </button>
                  </td>
                  <td>{pod.cost_per_hour != null ? `$${pod.cost_per_hour}` : "-"}</td>
                  <td className="text-right space-x-1 whitespace-nowrap">
                    <button
                      className={button}
                      onClick={() => setOpenSessions(openSessions === pod.id ? null : pod.id)}
                      title="Sessions"
                    >
                      <FaClock />
                    </button>
                    <button
                      className={button}
                      disabled={pod.status !== "RUNNING"}
                      onClick={() => navigate(`/${currentOrg?.prefix}/compute/${pod.id}/files`)}
                      title="Files"
                    >
                      <FaFolderOpen />
                    </button>
                    {pod.status === "RUNNING" ? (
                      <button className={button} disabled={busy === pod.id} onClick={() => act(pod, "stop")} title="Stop">
                        <FaStop />
                      </button>
                    ) : (
                      <button className={button} disabled={busy === pod.id} onClick={() => act(pod, "start")} title="Start">
                        <FaPlay />
                      </button>
                    )}
                    <button className={button} disabled={busy === pod.id} onClick={() => act(pod, "restart")} title="Restart">
                      <FaUndo />
                    </button>
                    <button className={button} disabled={busy === pod.id} onClick={() => act(pod, "terminate")} title="Terminate">
                      <FaTrash />
                    </button>
                  </td>
                </tr>
                {openSessions === pod.id && currentOrg && (
                  <tr>
                    <td colSpan={5}>
                      <PodSessions orgPrefix={currentOrg.prefix} podId={pod.id} />
                    </td>
                  </tr>
                )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </OrganizationNavbar>
  );
};

export default ComputePage;
