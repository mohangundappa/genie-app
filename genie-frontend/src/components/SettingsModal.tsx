import { useState, useEffect } from "react";
import { X, Key, Bot, Save, Loader2 } from "lucide-react";
import { useApi } from "../hooks/useApi";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const api = useApi();
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("gpt-4o-mini");
  const [hasKey, setHasKey] = useState(false);
  const [keyPreview, setKeyPreview] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (isOpen) {
      api.getSettings().then((settings) => {
        setHasKey(settings.has_api_key);
        setKeyPreview(settings.api_key_preview);
        setModel(settings.model);
      });
    }
  }, [isOpen]);

  const handleSave = async () => {
    setSaving(true);
    const updates: { openai_api_key?: string; openai_model?: string } = {};
    if (apiKey) updates.openai_api_key = apiKey;
    updates.openai_model = model;
    await api.updateSettings(updates);
    setSaving(false);
    setSaved(true);
    setTimeout(() => {
      setSaved(false);
      onClose();
    }, 1500);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-gray-900 border border-gray-700 rounded-xl shadow-2xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Bot className="w-5 h-5 text-indigo-400" />
            Settings
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2 flex items-center gap-2">
              <Key className="w-4 h-4 text-indigo-400" />
              OpenAI API Key
            </label>
            {hasKey && (
              <p className="text-xs text-green-400 mb-2">
                Current key: {keyPreview}
              </p>
            )}
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={hasKey ? "Enter new key to update..." : "sk-..."}
              className="w-full px-3 py-2.5 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none text-sm"
            />
            <p className="mt-1.5 text-xs text-gray-500">
              Required for AI-powered natural language queries. Get yours at{" "}
              <a
                href="https://platform.openai.com/api-keys"
                target="_blank"
                rel="noopener noreferrer"
                className="text-indigo-400 hover:text-indigo-300"
              >
                platform.openai.com
              </a>
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Model
            </label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full px-3 py-2.5 bg-gray-800 border border-gray-600 rounded-lg text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none text-sm"
            >
              <option value="gpt-4o-mini">GPT-4o Mini (Fast, Cost-effective)</option>
              <option value="gpt-4o">GPT-4o (Most Capable)</option>
              <option value="gpt-4-turbo">GPT-4 Turbo</option>
              <option value="gpt-3.5-turbo">GPT-3.5 Turbo (Fastest)</option>
            </select>
          </div>

          <div className="bg-gray-800/50 rounded-lg p-3 border border-gray-700">
            <p className="text-xs text-gray-400">
              Without an API key, Data Genie uses basic pattern matching for queries.
              With an API key, it uses advanced AI to understand complex natural language questions
              and generate accurate SQL queries.
            </p>
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-700">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
          >
            {saving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : saved ? (
              "Saved!"
            ) : (
              <>
                <Save className="w-4 h-4" />
                Save
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
