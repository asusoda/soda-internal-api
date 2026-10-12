import { useCallback, useEffect, useState, type ChangeEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "react-toastify";
import axios from "axios";
import { FaArrowLeft, FaDownload, FaFile, FaFolder, FaFolderPlus, FaPen, FaTrash, FaUpload } from "react-icons/fa";
import { useAuth } from "../components/auth/AuthContext";
import OrganizationNavbar from "../components/shared/OrganizationNavbar";
import ThemedLoading from "../components/ui/ThemedLoading";
import apiClient from "../components/utils/axios";
import { crumbs, formatSize, joinPath, parentPath } from "../utils/podPaths";
import type { PodFileEntry } from "../computeTypes";
import type { ApiError } from "../types";

const errorText = (error: unknown, fallback: string) =>
  (axios.isAxiosError<ApiError>(error) && error.response?.data?.error) || fallback;

// A text file open in the editor. POST /files/read gives the content and POST /files/write takes this body.
interface OpenFile {
  path: string;
  content: string;
}
const button = "px-3 py-1.5 rounded text-sm border border-gray-600 text-gray-200 hover:bg-gray-700 disabled:opacity-50";

const PodFilesPage = () => {
  const { currentOrg } = useAuth();
  const { podId } = useParams();
  const navigate = useNavigate();
  const [path, setPath] = useState("/workspace");
  const [entries, setEntries] = useState<PodFileEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<OpenFile | null>(null);
  const base = `/api/compute/${currentOrg?.prefix}/pods/${podId}/files`;

  const load = useCallback(
    async (target: string) => {
      if (!currentOrg) return;
      try {
        setLoading(true);
        const response = await apiClient.get<{ path: string; files: PodFileEntry[] }>(base, { params: { path: target } });
        setPath(response.data.path);
        setEntries(response.data.files || []);
      } catch (error) {
        toast.error(errorText(error, "Could not list the directory"));
      } finally {
        setLoading(false);
      }
    },
    [base, currentOrg]
  );

  useEffect(() => {
    load("/workspace");
  }, [load]);

  const run = async (call: () => Promise<unknown>, success?: string) => {
    try {
      await call();
      if (success) toast.success(success);
      await load(path);
    } catch (error) {
      toast.error(errorText(error, "The pod refused the request"));
    }
  };

  const open = async (entry: PodFileEntry) => {
    const target = joinPath(path, entry.name);
    if (entry.type === "directory") return load(target);
    try {
      const response = await apiClient.post<OpenFile>(`${base}/read`, { path: target });
      setEditing({ path: target, content: response.data.content });
    } catch (error) {
      toast.error(errorText(error, "Could not open the file"));
    }
  };

  const download = async (entry: PodFileEntry) => {
    try {
      const response = await apiClient.post<Blob>(`${base}/download`, { path: joinPath(path, entry.name) }, { responseType: "blob" });
      const url = URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = entry.name;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast.error("Could not download the file");
    }
  };

  const upload = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const form = new FormData();
    form.append("path", path);
    form.append("file", file);
    run(() => apiClient.post(`${base}/upload`, form), `Uploaded ${file.name}`);
  };

  const mkdir = () => {
    const name = window.prompt("New folder name");
    if (name) run(() => apiClient.post(`${base}/mkdir`, { path: joinPath(path, name) }));
  };

  const rename = (entry: PodFileEntry) => {
    const name = window.prompt("New name", entry.name);
    if (name && name !== entry.name) {
      run(() => apiClient.post(`${base}/rename`, { old_path: joinPath(path, entry.name), new_path: joinPath(path, name) }));
    }
  };

  const remove = (entry: PodFileEntry) => {
    if (window.confirm(`Delete ${joinPath(path, entry.name)}${entry.type === "directory" ? " and everything in it" : ""}?`)) {
      run(() => apiClient.post(`${base}/delete`, { path: joinPath(path, entry.name) }), "Deleted");
    }
  };

  const save = () =>
    run(async () => {
      await apiClient.post(`${base}/write`, editing);
      setEditing(null);
    }, "Saved");

  return (
    <OrganizationNavbar>
      <div className="max-w-6xl mx-auto px-4 py-8">
        <button className={`${button} mb-4`} onClick={() => navigate(`/${currentOrg?.prefix}/compute`)}>
          <FaArrowLeft className="inline mr-1" /> Pods
        </button>
        <h1 className="text-2xl font-bold text-white mb-4">Files on {podId}</h1>

        {editing ? (
          <div>
            <div className="text-gray-300 mb-2">{editing.path}</div>
            <textarea
              className="w-full h-96 p-3 font-mono text-sm rounded bg-gray-900 border border-gray-700 text-gray-100"
              value={editing.content}
              onChange={(e) => setEditing({ ...editing, content: e.target.value })}
            />
            <div className="mt-2 space-x-2">
              <button className={button} onClick={save}>
                Save
              </button>
              <button className={button} onClick={() => setEditing(null)}>
                Close
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between mb-3">
              <div className="text-gray-300 text-sm">
                {crumbs(path).map((crumb, i) => (
                  <span key={crumb.path}>
                    {i > 1 && "/"}
                    <button className="hover:underline" onClick={() => load(crumb.path)}>
                      {crumb.name}
                    </button>
                  </span>
                ))}
              </div>
              <div className="space-x-2">
                <button className={button} onClick={mkdir} title="New folder">
                  <FaFolderPlus />
                </button>
                <label className={`${button} cursor-pointer`} title="Upload">
                  <FaUpload className="inline" />
                  <input type="file" className="hidden" onChange={upload} />
                </label>
              </div>
            </div>
            {loading ? (
              <ThemedLoading message="Loading files..." />
            ) : (
              <table className="w-full text-sm text-left text-gray-300">
                <tbody>
                  {path !== "/" && (
                    <tr className="border-b border-gray-800">
                      <td className="py-2" colSpan={4}>
                        <button className="hover:underline" onClick={() => load(parentPath(path))}>
                          ..
                        </button>
                      </td>
                    </tr>
                  )}
                  {entries.map((entry) => (
                    <tr key={entry.name} className="border-b border-gray-800">
                      <td className="py-2">
                        <button className="hover:underline flex items-center" onClick={() => open(entry)}>
                          {entry.type === "directory" ? <FaFolder className="mr-2 text-yellow-400" /> : <FaFile className="mr-2" />}
                          {entry.name}
                        </button>
                      </td>
                      <td>{entry.type === "file" ? formatSize(entry.size) : ""}</td>
                      <td>{entry.permissions}</td>
                      <td className="text-right space-x-1 whitespace-nowrap">
                        {entry.type === "file" && (
                          <button className={button} onClick={() => download(entry)} title="Download">
                            <FaDownload />
                          </button>
                        )}
                        <button className={button} onClick={() => rename(entry)} title="Rename">
                          <FaPen />
                        </button>
                        <button className={button} onClick={() => remove(entry)} title="Delete">
                          <FaTrash />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </div>
    </OrganizationNavbar>
  );
};

export default PodFilesPage;
