"use client";

import { useEffect, useRef } from "react";
import { createClient } from "@/utils/supabase/client";
import { useRouter } from "next/navigation";

export default function SessionManager() {
  const router = useRouter();
  const checking = useRef(false);

  useEffect(() => {
    // Tab Close / New Tab logic:
    // If we open a new tab, sessionStorage is empty. We can clear Supabase auth to force a new login.
    const isReturningTab = sessionStorage.getItem("tab_session_active");
    if (!isReturningTab) {
       sessionStorage.setItem("tab_session_active", "true");
       for (let i = 0; i < localStorage.length; i++) {
         const key = localStorage.key(i);
         if (key && key.startsWith("sb-") && key.endsWith("-auth-token")) {
           localStorage.removeItem(key);
         }
       }
       const supabase = createClient();
       supabase.auth.signOut().then(() => {
           window.location.reload();
       });
    }

    // 2. Poll the backend every 5s to check if the server restarted
    let lastBootId: string | null = null;
    const checkServerRestart = async () => {
      if (checking.current) return;
      checking.current = true;
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
        const res = await fetch(`${apiUrl}/api/health`, { cache: "no-store" });
        if (res.ok) {
          const data = await res.json();
          if (lastBootId === null) {
            lastBootId = data.boot_id;
          } else if (lastBootId !== data.boot_id) {
            console.log("Server restart detected! Logging out...");
            const supabase = createClient();
            await supabase.auth.signOut();
            window.location.href = "/login";
          }
        }
      } catch (err) {
        // server might be down temporarily
      } finally {
        checking.current = false;
      }
    };

    const interval = setInterval(checkServerRestart, 5000); // Check every 5 seconds for fast detection
    checkServerRestart();

    return () => clearInterval(interval);
  }, []);

  return null;
}
