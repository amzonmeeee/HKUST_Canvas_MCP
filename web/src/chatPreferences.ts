import { useEffect, useState } from "react";

export type SendShortcut = "enter" | "mod-enter";
const key = "canvas-workbench.send-shortcut";
function read(): SendShortcut {
  try {
    return localStorage.getItem(key) === "enter" ? "enter" : "mod-enter";
  } catch {
    return "mod-enter";
  }
}
export function useSendShortcut() {
  const [shortcut, setShortcut] = useState<SendShortcut>(read);
  useEffect(() => {
    const update = () => setShortcut(read());
    window.addEventListener("storage", update);
    window.addEventListener("canvas-chat-preference", update);
    return () => {
      window.removeEventListener("storage", update);
      window.removeEventListener("canvas-chat-preference", update);
    };
  }, []);
  function save(value: SendShortcut) {
    setShortcut(value);
    try {
      localStorage.setItem(key, value);
    } catch {
      /* Browser preference. */
    }
    window.dispatchEvent(new Event("canvas-chat-preference"));
  }
  return [shortcut, save] as const;
}
