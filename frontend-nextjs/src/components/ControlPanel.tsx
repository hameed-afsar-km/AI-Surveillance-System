"use client";

import { useState, useEffect } from "react";
import { Play, Square, Settings2, Shield, Radio, Volume2, Cpu, Loader2, Mail, X, Check, Save } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "@/lib/api";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface Props {
  running: boolean;
  starting: boolean;
  soundEnabled: boolean;
  aiEnabled: boolean;
  backendOnline: boolean;
  error: string | null;
  onStart: (mode: string, source: string) => Promise<void>;
  onStop: () => Promise<void>;
  onSoundToggle: (v: boolean) => Promise<void>;
  onAiToggle: (v: boolean) => Promise<void>;
}

export default function ControlPanel({
  running, starting, soundEnabled, aiEnabled, backendOnline,
  error, onStart, onStop, onSoundToggle, onAiToggle,
}: Props) {
  const [mode, setMode] = useState<"simulation" | "webcam">("simulation");
  const [videoFiles, setVideoFiles] = useState<string[]>([]);
  const [videoFile, setVideoFile] = useState("");
  const [camIdx, setCamIdx] = useState(0);

  // Settings Modal State
  const [showSettings, setShowSettings] = useState(false);
  const [emailConfig, setEmailConfig] = useState({
    email_sender: "",
    email_password: "",
    email_accident: "",
    email_fire: "",
    email_garbage: "",
    email_health: "",
    email_traffic: "",
    phone_accident: "",
    phone_fire: "",
    phone_garbage: "",
    phone_health: "",
    phone_traffic: "",
  });
  const [savingSettings, setSavingSettings] = useState(false);
  const [testStatus, setTestStatus] = useState<null | "loading" | "success" | "error">(null);
  const [testError, setTestError] = useState("");

  // Derived mail toggle (whether sender and password exist)
  const mailEnabled = Boolean(emailConfig.email_sender && emailConfig.email_password);

  useEffect(() => {
    const fetchInitData = async () => {
      const files = await api.getVideos();
      if (files && files.length > 0) {
        setVideoFiles(files);
        setVideoFile(files[0]);
      }
      const settings = await api.getSettings();
      if (settings) {
        setEmailConfig({
          email_sender: settings.email_sender || "",
          email_password: settings.email_password || "",
          email_accident: settings.email_accident || "",
          email_fire: settings.email_fire || "",
          email_garbage: settings.email_garbage || "",
          email_health: settings.email_health || "",
          email_traffic: settings.email_traffic || "",
          phone_accident: settings.phone_accident || "",
          phone_fire: settings.phone_fire || "",
          phone_garbage: settings.phone_garbage || "",
          phone_health: settings.phone_health || "",
          phone_traffic: settings.phone_traffic || "",
        });
      }
    };
    if (backendOnline) fetchInitData();
  }, [backendOnline]);

  const handleStart = () => onStart(mode === "simulation" ? "file" : "webcam", mode === "simulation" ? videoFile : String(camIdx));

  const saveConfig = async () => {
    setSavingSettings(true);
    await api.settings(emailConfig);
    setSavingSettings(false);
    setShowSettings(false);
  };

  const handleTestEmail = async (alert_type: string = "test_connection") => {
    if (!emailConfig.email_sender || !emailConfig.email_password) {
      setTestStatus("error");
      setTestError("Need Sender Email & Password first.");
      return;
    }
    setTestStatus("loading");
    setTestError("");
    const res = await api.testEmail({ ...emailConfig, alert_type });
    if (res && !res.error) {
      setTestStatus("success");
      setTimeout(() => setTestStatus(null), 4000);
    } else {
      setTestStatus("error");
      setTestError(res?.error || "Connection Failed.");
    }
  };

  const [customDepts, setCustomDepts] = useState<{label: string, icon: string, key: string, phoneKey: string}[]>([]);
  const [showAddDeptModal, setShowAddDeptModal] = useState(false);
  const [newDeptName, setNewDeptName] = useState("");
  const [newDeptPhone, setNewDeptPhone] = useState("");
  
  const handleAddCategory = () => {
    if (!newDeptName.trim()) return;
    const key = `email_custom_${Date.now()}`;
    const pKey = `phone_custom_${Date.now()}`;
    setCustomDepts(prev => [...prev, { label: newDeptName.trim(), icon: "📁", key, phoneKey: pKey }]);
    setEmailConfig(prev => ({ ...prev, [key]: "", [pKey]: "" }));
    setNewDeptName("");
    setNewDeptPhone("");
    setShowAddDeptModal(false);
  };

  const handleMailToggle = () => {
    if (!mailEnabled) setShowSettings(true);
    else {
      // Prompt user or clear to disable
      if (window.confirm("Disable Email Dispatch by clearing the Sender Email?")) {
        const newConf = { ...emailConfig, email_sender: "", email_password: "" };
        setEmailConfig(newConf);
        api.settings(newConf);
      }
    }
  };

  return (
    <>
      <div className="clean-panel p-6 flex flex-col gap-6 select-none relative">
        <div className="flex justify-between items-center mb-1">
          <div className="flex items-center gap-2">
             <Settings2 size={16} className="text-[#a1a1aa]" />
             <h2 className="text-sm font-semibold tracking-tight text-[#fafafa]">Operations Control</h2>
          </div>
          <button 
            onClick={() => setShowSettings(true)}
            className="w-8 h-8 flex items-center justify-center rounded bg-[#18181b] border border-[#27272a] text-[#a1a1aa] hover:text-[#fafafa] hover:bg-[#27272a] transition-all"
            title="Configure Mail Routing"
          >
            <Mail size={14} />
          </button>
        </div>
        
        <div className="space-y-4">
          <div className="flex bg-[#09090b] p-1 rounded-lg border border-[#27272a] relative overflow-hidden">
             {/* Slider Background */}
             <motion.div 
               className="absolute top-1 bottom-1 bg-[#27272a] rounded-md border border-[#3f3f46] shadow-sm"
               initial={false}
               animate={{ 
                 left: mode === "simulation" ? "4px" : "50%", 
                 width: "calc(50% - 4px)" 
               }}
               transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
             />
             
            <button
              onClick={() => setMode("simulation")}
              className={cn(
                "flex-1 py-1.5 text-[13px] font-medium z-10 transition-colors",
                mode === "simulation" ? "text-[#fafafa]" : "text-[#a1a1aa] hover:text-[#d4d4d8]"
              )}
            >
              Simulation
            </button>
            <button
              onClick={() => setMode("webcam")}
              className={cn(
                "flex-1 py-1.5 text-[13px] font-medium z-10 transition-colors",
                mode === "webcam" ? "text-[#fafafa]" : "text-[#a1a1aa] hover:text-[#d4d4d8]"
              )}
            >
              Live Cam
            </button>
          </div>

          <motion.div 
            layout
            className="space-y-2"
          >
            <label className="block text-[11px] font-semibold text-[#a1a1aa] uppercase tracking-wider">
              {mode === "simulation" ? "Target Repository" : "Webcam Interface"}
            </label>
            <AnimatePresence mode="wait">
              {mode === "simulation" ? (
                <motion.select
                  key="sim-select"
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -5 }}
                  value={videoFile}
                  onChange={(e) => setVideoFile(e.target.value)}
                  className="w-full bg-[#09090b] border border-[#27272a] rounded-lg px-3 py-2.5 text-sm text-[#fafafa] focus:outline-none focus:ring-1 focus:ring-blue-500/50 transition-all appearance-none cursor-pointer"
                >
                  {videoFiles.map((v) => <option key={v} value={v}>{v}</option>)}
                </motion.select>
              ) : (
                <motion.input
                  key="webcam-idx"
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -5 }}
                  type="number" min={0} max={9}
                  value={camIdx}
                  onChange={(e) => setCamIdx(Number(e.target.value))}
                  className="w-full bg-[#09090b] border border-[#27272a] rounded-lg px-3 py-2.5 text-sm text-[#fafafa] focus:outline-none focus:ring-1 focus:ring-blue-500/50 transition-all"
                 />
              )}
            </AnimatePresence>
          </motion.div>
        </div>

        <div className="flex gap-3 mt-2">
          <motion.button
            whileHover={!running && !starting && backendOnline ? { scale: 1.02, y: -1 } : {}}
            whileTap={!running && !starting && backendOnline ? { scale: 0.98 } : {}}
            onClick={handleStart}
            disabled={running || starting || !backendOnline}
            className={cn(
              "flex-1 py-2.5 rounded-lg flex items-center justify-center gap-2 text-sm font-semibold transition-all relative overflow-hidden",
              running || starting
                ? "bg-[#18181b] text-[#52525b] cursor-default border border-[#27272a]"
                : "bg-blue-600 hover:bg-blue-500 text-white shadow-[0_0_20px_rgba(37,99,235,0.2)]"
            )}
          >
            {(running || starting) && (
               <motion.div
                 className="absolute inset-0 bg-white/5"
                 animate={{ opacity: [0.1, 0.3, 0.1] }}
                 transition={{ duration: 2, repeat: Infinity }}
               />
            )}
            {starting ? (
              <><Loader2 size={16} className="animate-spin" /> Initialising…</>
            ) : running ? (
              <><Play size={16} fill="currentColor" /> Engaged</>
            ) : (
              <><Play size={16} fill="white" /> Engage</>
            )}
          </motion.button>

          <motion.button
            whileHover={running ? { scale: 1.02, y: -1 } : {}}
            whileTap={running ? { scale: 0.98 } : {}}
            onClick={onStop}
            disabled={!running}
            className={cn(
               "flex-1 py-2.5 rounded-lg flex items-center justify-center gap-2 text-sm font-semibold transition-all",
               running
                 ? "bg-[#450a0a] hover:bg-[#7f1d1d] text-[#fca5a5] border border-[#7f1d1d] shadow-[0_0_20px_rgba(127,29,29,0.2)]"
                 : "bg-[#18181b] text-[#52525b] border border-[#27272a] opacity-50 cursor-not-allowed"
            )}
          >
            <Square size={16} fill="currentColor" /> Terminate
          </motion.button>
        </div>

        {error && (
          <motion.div 
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-[#450a0a] text-[#fca5a5] px-3 py-3 rounded-lg border border-[#7f1d1d] text-[13px] flex items-start gap-2"
          >
            <Shield size={14} className="mt-0.5 shrink-0" />
            <div className="leading-tight">{error}</div>
          </motion.div>
        )}

        <div className="pt-2 border-t border-[#27272a]">
          <h3 className="text-[11px] font-bold tracking-widest text-[#52525b] uppercase mb-4 mt-2">Active Subroutines</h3>
          
          <div className="space-y-4">
            <SubroutineToggle 
               icon={<Volume2 size={16}/>}
               label="Acoustic Pulse"
               active={soundEnabled}
               onToggle={() => onSoundToggle(!soundEnabled)}
            />
            <SubroutineToggle 
               icon={<Cpu size={16}/>}
               label="Neural Insight"
               active={aiEnabled}
               onToggle={() => onAiToggle(!aiEnabled)}
            />
            <SubroutineToggle 
               icon={<Mail size={16}/>}
               label="Email Dispatch"
               active={mailEnabled}
               onToggle={handleMailToggle}
               warning={!mailEnabled}
            />
          </div>
        </div>
      </div>

      <AnimatePresence>
        {showSettings && (
          <motion.div 
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
          >
            <motion.div 
              initial={{ scale: 0.95, y: 20 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.95, y: 20 }}
              className="bg-[#09090b] border border-[#27272a] rounded-xl w-full max-w-lg shadow-2xl overflow-hidden flex flex-col max-h-[90vh]"
            >
              <div className="p-4 border-b border-[#27272a] flex justify-between items-center bg-[#18181b]">
                <h2 className="text-lg font-bold text-[#fafafa] flex items-center gap-2">
                  <Mail size={18} className="text-blue-500" /> Ministry Mail Routing
                </h2>
                <button onClick={() => setShowSettings(false)} className="text-[#a1a1aa] hover:text-white"><X size={18} /></button>
              </div>
              
              <div className="p-6 overflow-y-auto space-y-6 form-dark flex-1">
                <div className="space-y-3">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-1.5 h-4 bg-blue-500 rounded-full"></div>
                    <h3 className="text-sm font-semibold tracking-wide text-white uppercase">Sender Identity</h3>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-[12px] text-[#a1a1aa] mb-1.5 block">Sender Email</label>
                      <input type="email" value={emailConfig.email_sender} onChange={e => setEmailConfig(p => ({...p, email_sender: e.target.value}))} placeholder="system@nexus.ai" className="w-full bg-[#18181b] border border-[#27272a] rounded px-3 py-2 text-sm focus:border-blue-500 outline-none transition-colors" />
                    </div>
                    <div>
                      <label className="text-[12px] text-[#a1a1aa] mb-1.5 block">App Password</label>
                      <input type="password" value={emailConfig.email_password} onChange={e => setEmailConfig(p => ({...p, email_password: e.target.value}))} placeholder="••••••••" className="w-full bg-[#18181b] border border-[#27272a] rounded px-3 py-2 text-sm focus:border-blue-500 outline-none transition-colors" />
                    </div>
                  </div>
                  <p className="text-[11px] text-[#52525b]">For Gmail, use a 16-character App Password, not your standard account password.</p>
                </div>

                <div className="space-y-3">
                   <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <div className="w-1.5 h-4 bg-blue-500 rounded-full"></div>
                      <h3 className="text-sm font-semibold tracking-wide text-white uppercase">Department Routing</h3>
                    </div>
                    <button onClick={() => setShowAddDeptModal(true)} className="text-[10px] bg-blue-600/20 text-blue-400 border border-blue-500/30 px-2 py-1 rounded hover:bg-blue-600/40 transition-all font-bold">+ ADD CATEGORY</button>
                  </div>

                  <div className="space-y-4">
                    <DeptInput 
                      label="Police / Traffic" icon="🚔" 
                      email={emailConfig.email_accident} onEmailChange={v => setEmailConfig(p => ({...p, email_accident: v}))}
                      phone={emailConfig.phone_accident} onPhoneChange={v => setEmailConfig(p => ({...p, phone_accident: v}))}
                      onTest={() => handleTestEmail("collision")} 
                    />
                    <DeptInput 
                      label="Fire Department" icon="🔥" 
                      email={emailConfig.email_fire} onEmailChange={v => setEmailConfig(p => ({...p, email_fire: v}))}
                      phone={emailConfig.phone_fire} onPhoneChange={v => setEmailConfig(p => ({...p, phone_fire: v}))}
                      onTest={() => handleTestEmail("fire_hazard")} 
                    />
                    <DeptInput 
                      label="Garbage/Municipal" icon="🗑️" 
                      email={emailConfig.email_garbage} onEmailChange={v => setEmailConfig(p => ({...p, email_garbage: v}))}
                      phone={emailConfig.phone_garbage} onPhoneChange={v => setEmailConfig(p => ({...p, phone_garbage: v}))}
                      onTest={() => handleTestEmail("littering")} 
                    />
                    <DeptInput 
                      label="Health Department" icon="🚑" 
                      email={emailConfig.email_health} onEmailChange={v => setEmailConfig(p => ({...p, email_health: v}))}
                      phone={emailConfig.phone_health} onPhoneChange={v => setEmailConfig(p => ({...p, phone_health: v}))}
                      onTest={() => handleTestEmail("medical_emergency")} 
                    />
                    
                    {customDepts.map(d => (
                      <DeptInput 
                        key={d.key} label={d.label} icon={d.icon} 
                        email={emailConfig[d.key as keyof typeof emailConfig] as string} onEmailChange={v => setEmailConfig(p => ({...p, [d.key]: v}))}
                        phone={emailConfig[d.phoneKey as keyof typeof emailConfig] as string} onPhoneChange={v => setEmailConfig(p => ({...p, [d.phoneKey]: v}))}
                        onTest={() => handleTestEmail("test_connection")} 
                      />
                    ))}
                  </div>
                </div>
              </div>

              <div className="p-4 border-t border-[#27272a] bg-[#18181b] flex items-center justify-between shrink-0">
                <div className="flex-1 mr-4">
                  <AnimatePresence mode="wait">
                    {testStatus === "loading" && (
                      <motion.div key="l" initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}} className="flex items-center gap-2 text-[12px] text-blue-400">
                        <Loader2 size={12} className="animate-spin" /> Verifying Connection...
                      </motion.div>
                    )}
                    {testStatus === "success" && (
                      <motion.div key="s" initial={{opacity:0, x:-5}} animate={{opacity:1, x:0}} className="flex items-center gap-2 text-[12px] text-emerald-500 font-bold">
                        <Check size={12} /> Test Alert Sent!
                      </motion.div>
                    )}
                    {testStatus === "error" && (
                      <motion.div key="e" initial={{opacity:0, x:-5}} animate={{opacity:1, x:0}} className="text-[11px] text-red-500 font-medium leading-tight max-w-[180px]">
                         {testError}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
                
                <div className="flex gap-3">
                  <button 
                    onClick={() => handleTestEmail()} 
                    disabled={testStatus === "loading" || !emailConfig.email_sender}
                    className="px-4 py-2 text-sm font-medium text-[#fafafa] bg-[#27272a] hover:bg-[#3f3f46] rounded flex items-center gap-2 transition-all disabled:opacity-30"
                  >
                    Global Test
                  </button>
                  <button onClick={saveConfig} disabled={savingSettings} className="bg-blue-600 hover:bg-blue-500 text-white px-5 py-2 text-sm font-semibold rounded shadow-lg flex items-center gap-2 transition-all disabled:opacity-50">
                    {savingSettings ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                    Apply Config
                  </button>
                </div>
              </div>
            </motion.div>

            {/* Sub-Modal for adding category */}
            <AnimatePresence>
              {showAddDeptModal && (
                <motion.div 
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                  className="fixed inset-0 z-[110] flex items-center justify-center p-4 bg-black/40 backdrop-blur-[2px]"
                >
                  <motion.div 
                    initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.9, opacity: 0 }}
                    className="bg-[#18181b] border border-[#3f3f46] rounded-xl p-6 w-full max-w-sm shadow-2xl space-y-4"
                  >
                    <div>
                      <h3 className="text-lg font-bold text-white mb-1">New Ministry / Dept</h3>
                      <p className="text-xs text-[#a1a1aa]">Register a custom alert category for the AI surveillance suite.</p>
                    </div>
                    <div className="space-y-3">
                      <div>
                        <label className="text-[10px] text-[#a1a1aa] uppercase font-bold mb-1 block">Department Name</label>
                        <input 
                          autoFocus
                          placeholder="e.g. Navigation Branch"
                          value={newDeptName}
                          onChange={e => setNewDeptName(e.target.value)}
                          className="w-full bg-[#09090b] border border-[#27272a] rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 outline-none transition-all"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-[#a1a1aa] uppercase font-bold mb-1 block">Primary Phone (SMS)</label>
                        <input 
                          placeholder="+1 234 567 8900"
                          value={newDeptPhone}
                          onChange={e => setNewDeptPhone(e.target.value)}
                          onKeyDown={e => e.key === "Enter" && handleAddCategory()}
                          className="w-full bg-[#09090b] border border-[#27272a] rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 outline-none transition-all"
                        />
                      </div>
                    </div>
                    <div className="flex gap-3 pt-2">
                       <button onClick={() => setShowAddDeptModal(false)} className="flex-1 px-4 py-2 text-sm text-[#a1a1aa] hover:text-white transition-colors">Cancel</button>
                       <button onClick={handleAddCategory} className="flex-1 bg-blue-600 hover:bg-blue-500 text-white font-semibold py-2 rounded text-sm transition-all">Add Dept</button>
                    </div>
                  </motion.div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

function DeptInput({ 
  label, icon, email, onEmailChange, phone, onPhoneChange, onTest 
}: { 
  label: string, icon: string, 
  email: string, onEmailChange: (v: string) => void,
  phone: string, onPhoneChange: (v: string) => void,
  onTest: () => void 
}) {
  return (
    <div className="flex flex-col gap-1.5 p-3 rounded-lg bg-[#18181b]/50 border border-[#27272a] hover:border-[#3f3f46] transition-colors group/item">
      <div className="flex items-center justify-between mb-0.5">
        <div className="flex items-center gap-2">
           <span className="grayscale group-hover/item:grayscale-0 transition-all">{icon}</span>
           <span className="text-[11px] font-bold text-[#fafafa] uppercase tracking-wider">{label}</span>
        </div>
        <button 
          onClick={onTest}
          disabled={!email && !phone}
          title={`Test ${label} Channels`}
          className="text-[#52525b] hover:text-emerald-400 transition-colors disabled:opacity-0"
        >
          <Radio size={14} />
        </button>
      </div>
      
      <div className="grid grid-cols-2 gap-2">
        <input 
          placeholder="Email Address"
          value={email}
          onChange={(e) => onEmailChange(e.target.value)}
          className="w-full bg-[#09090b] border border-[#27272a] rounded px-2 py-1 text-[12px] text-white focus:border-blue-500 outline-none transition-colors placeholder-[#3f3f46]"
        />
        <input 
          placeholder="SMS (Mobile)"
          value={phone}
          onChange={(e) => onPhoneChange(e.target.value)}
          className="w-full bg-[#09090b] border border-[#27272a] rounded px-2 py-1 text-[12px] text-white focus:border-blue-500 outline-none transition-all placeholder-[#3f3f46]"
        />
      </div>
    </div>
  );
}

function SubroutineToggle({ icon, label, active, onToggle, warning }: { icon: React.ReactNode, label: string, active: boolean, onToggle: () => void, warning?: boolean }) {
  return (
    <label className="flex items-center justify-between cursor-pointer group">
      <div className="flex items-center gap-3">
        <span className={cn("transition-colors", active ? "text-blue-400" : (warning ? "text-yellow-500" : "text-[#52525b]"))}>
          {icon}
        </span>
        <span className="text-[13px] font-medium text-[#fafafa]">{label}</span>
      </div>
      <div 
        onClick={onToggle}
        className={cn(
          "w-10 h-[22px] rounded-full transition-all p-1 relative",
          active ? 'bg-blue-600 shadow-[0_0_10px_rgba(37,99,235,0.3)]' : 'bg-[#18181b] border border-[#27272a]'
        )}
      >
        <motion.div 
          className="absolute top-1 w-3.5 h-3.5 bg-white rounded-full shadow-lg"
          animate={{ x: active ? 18 : 2 }}
          transition={{ type: "spring", stiffness: 500, damping: 30 }}
        />
      </div>
    </label>
  );
}
