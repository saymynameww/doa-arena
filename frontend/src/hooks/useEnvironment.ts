import { useCallback, useEffect, useState } from "react";
import { getEnvironment, refreshEnvironment } from "@/services/api";
import type { EnvironmentStatus } from "@/types/generated";

export default function useEnvironment() {
  const [environment, setEnvironment] = useState<EnvironmentStatus>({ status: "detecting" });
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const result = await getEnvironment();
        if (!active) return;
        setEnvironment(result);
        // 这里只读取服务器快照，不启动新的探测进程。
        if (result.status === "detecting") timer = setTimeout(() => void poll(), 500);
      } catch {
        if (active) setEnvironment({ status: "error", error: "读取环境信息失败，请检查服务后重新检测" });
      }
    };
    void poll();
    return () => { active = false; clearTimeout(timer); };
  }, [revision]);

  const refresh = useCallback(async () => {
    setEnvironment({ status: "detecting" });
    try {
      await refreshEnvironment();
      setRevision((value) => value + 1);
    } catch {
      setEnvironment({ status: "error", error: "重新检测失败，请检查后端服务" });
    }
  }, []);
  const deviceLabel = environment.status === "detecting" ? "CUDA（检测中）"
    : environment.status === "error" ? "CUDA（检测失败）"
    : environment.cuda_available ? "CUDA" : "CUDA（当前环境不可用）";
  return { environment, refresh, deviceLabel };
}
