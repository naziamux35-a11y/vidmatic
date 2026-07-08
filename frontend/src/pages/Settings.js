import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../utils/api';
import { toast } from 'sonner';
import { ArrowLeft, KeyRound, Loader2, CheckCircle, Film, Image as ImageIcon, ExternalLink } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';

const Settings = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [keys, setKeys] = useState({ pexels: null, pixabay: null, has_pexels: false, has_pixabay: false });
  const [pexelsInput, setPexelsInput] = useState('');
  const [pixabayInput, setPixabayInput] = useState('');

  useEffect(() => {
    api.get('/settings/stock-keys')
      .then(res => setKeys(res.data))
      .catch(err => { if (err.response?.status === 401) navigate('/auth'); })
      .finally(() => setLoading(false));
  }, [navigate]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = {};
      if (pexelsInput.trim()) payload.pexels_api_key = pexelsInput.trim();
      if (pixabayInput.trim()) payload.pixabay_api_key = pixabayInput.trim();
      if (Object.keys(payload).length === 0) {
        toast.info('Enter an API key to save');
        setSaving(false);
        return;
      }
      await api.put('/settings/stock-keys', payload);
      toast.success('API keys verified and saved!');
      const res = await api.get('/settings/stock-keys');
      setKeys(res.data);
      setPexelsInput('');
      setPixabayInput('');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save API keys');
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async (provider) => {
    try {
      await api.put('/settings/stock-keys', { [`${provider}_api_key`]: '' });
      toast.success(`${provider.charAt(0).toUpperCase() + provider.slice(1)} key removed`);
      const res = await api.get('/settings/stock-keys');
      setKeys(res.data);
    } catch {
      toast.error('Failed to remove key');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      <header className="border-b border-zinc-800 bg-zinc-900/50 backdrop-blur-xl sticky top-0 z-40">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-4 flex items-center gap-4">
          <button onClick={() => navigate('/dashboard')} className="p-2 hover:bg-zinc-800 rounded-lg transition-colors" data-testid="settings-back-btn">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-xl font-bold">Settings</h1>
            <p className="text-sm text-zinc-400">Manage your account and API keys</p>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-8 space-y-6">
        <div className="bg-zinc-900 rounded-2xl border border-zinc-800 p-6" data-testid="stock-keys-card">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-full bg-indigo-600/20 flex items-center justify-center">
              <KeyRound className="w-5 h-5 text-indigo-400" />
            </div>
            <div>
              <h2 className="text-lg font-bold">Your Stock Media API Keys</h2>
              <p className="text-sm text-zinc-400">Use your own free API keys for copyright-free, watermark-free stock footage</p>
            </div>
          </div>

          <div className="mt-6 space-y-6">
            {/* Pexels */}
            <div className="p-4 rounded-xl border border-zinc-700 bg-zinc-800/40">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Film className="w-4 h-4 text-emerald-400" />
                  <span className="font-medium">Pexels API Key</span>
                  {keys.has_pexels && (
                    <span className="flex items-center gap-1 text-xs text-emerald-400 bg-emerald-500/20 px-2 py-0.5 rounded-full">
                      <CheckCircle className="w-3 h-3" /> Active
                    </span>
                  )}
                </div>
                <a href="https://www.pexels.com/api/" target="_blank" rel="noreferrer" className="text-xs text-indigo-400 hover:underline flex items-center gap-1">
                  Get free key <ExternalLink className="w-3 h-3" />
                </a>
              </div>
              {keys.has_pexels && <p className="text-xs text-zinc-500 mb-2 font-mono">{keys.pexels}</p>}
              <div className="flex gap-2">
                <Input
                  data-testid="pexels-key-input"
                  value={pexelsInput}
                  onChange={(e) => setPexelsInput(e.target.value)}
                  placeholder={keys.has_pexels ? 'Enter new key to replace' : 'Paste your Pexels API key'}
                  className="bg-zinc-800 border-zinc-700"
                />
                {keys.has_pexels && (
                  <Button variant="outline" className="border-zinc-600 text-red-400 hover:bg-red-500/10" onClick={() => handleRemove('pexels')} data-testid="remove-pexels-btn">
                    Remove
                  </Button>
                )}
              </div>
            </div>

            {/* Pixabay */}
            <div className="p-4 rounded-xl border border-zinc-700 bg-zinc-800/40">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <ImageIcon className="w-4 h-4 text-blue-400" />
                  <span className="font-medium">Pixabay API Key</span>
                  {keys.has_pixabay && (
                    <span className="flex items-center gap-1 text-xs text-emerald-400 bg-emerald-500/20 px-2 py-0.5 rounded-full">
                      <CheckCircle className="w-3 h-3" /> Active
                    </span>
                  )}
                </div>
                <a href="https://pixabay.com/api/docs/" target="_blank" rel="noreferrer" className="text-xs text-indigo-400 hover:underline flex items-center gap-1">
                  Get free key <ExternalLink className="w-3 h-3" />
                </a>
              </div>
              {keys.has_pixabay && <p className="text-xs text-zinc-500 mb-2 font-mono">{keys.pixabay}</p>}
              <div className="flex gap-2">
                <Input
                  data-testid="pixabay-key-input"
                  value={pixabayInput}
                  onChange={(e) => setPixabayInput(e.target.value)}
                  placeholder={keys.has_pixabay ? 'Enter new key to replace' : 'Paste your Pixabay API key'}
                  className="bg-zinc-800 border-zinc-700"
                />
                {keys.has_pixabay && (
                  <Button variant="outline" className="border-zinc-600 text-red-400 hover:bg-red-500/10" onClick={() => handleRemove('pixabay')} data-testid="remove-pixabay-btn">
                    Remove
                  </Button>
                )}
              </div>
            </div>

            <Button
              onClick={handleSave}
              disabled={saving || (!pexelsInput.trim() && !pixabayInput.trim())}
              className="w-full bg-indigo-600 hover:bg-indigo-500 py-3"
              data-testid="save-stock-keys-btn"
            >
              {saving ? (<><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Verifying keys...</>) : 'Verify & Save Keys'}
            </Button>

            <p className="text-xs text-zinc-500">
              Keys are verified against the provider before saving. When set, your videos are generated with footage from your own accounts — always copyright-free and watermark-free. If not set, Vidmatic's built-in Pexels library is used.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Settings;
