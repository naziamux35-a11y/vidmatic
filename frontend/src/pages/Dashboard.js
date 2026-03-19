import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import api from '../utils/api';
import { toast } from 'sonner';
import { PlayCircle, Video, Upload, Eye, Youtube, Menu, X, LogOut, BarChart3, CreditCard, Settings as SettingsIcon, Shield, Sparkles, ArrowRight, CheckCircle, Calendar } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Progress } from '../components/ui/progress';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';

const Dashboard = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [user, setUser] = useState(location.state?.user || null);
  const [loading, setLoading] = useState(!location.state?.user);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(1);
  const [channels, setChannels] = useState([]);
  const [stats, setStats] = useState({ videos: 0, published: 0, views: '0', channels: 0 });
  
  // Video generation state
  const [videoPrompt, setVideoPrompt] = useState('');
  const [videoLength, setVideoLength] = useState('medium');
  const [voiceStyle, setVoiceStyle] = useState('professional');
  const [visualStyle, setVisualStyle] = useState('cinematic');
  
  useEffect(() => {
    if (location.state?.user) return;
    
    const checkAuth = async () => {
      try {
        const response = await api.get('/auth/me');
        setUser(response.data);
      } catch (error) {
        navigate('/');
      } finally {
        setLoading(false);
      }
    };
    checkAuth();
  }, [location, navigate]);
  
  useEffect(() => {
    if (user) {
      fetchChannels();
    }
  }, [user]);
  
  // Handle YouTube OAuth callback results from URL params
  useEffect(() => {
    const searchParams = new URLSearchParams(location.search);
    const youtubeConnected = searchParams.get('youtube_connected');
    const youtubeError = searchParams.get('youtube_error');
    const channelId = searchParams.get('channel_id');
    
    if (youtubeConnected === 'true') {
      toast.success('YouTube channel connected successfully!');
      fetchChannels(); // Refresh channels list
      // Clean up URL params
      window.history.replaceState({}, document.title, '/dashboard');
    }
    
    if (youtubeError) {
      toast.error(`YouTube connection failed: ${youtubeError.replace(/_/g, ' ')}`);
      // Clean up URL params
      window.history.replaceState({}, document.title, '/dashboard');
    }
  }, [location.search]);
  
  const fetchChannels = async () => {
    try {
      const response = await api.get('/youtube/channels');
      setChannels(response.data);
      // Update stats with real channel count
      setStats(prev => ({ ...prev, channels: response.data.length }));
    } catch (error) {
      console.error('Failed to fetch channels:', error);
    }
  };
  
  const handleLogout = async () => {
    try {
      await api.post('/auth/logout');
      navigate('/');
    } catch (error) {
      console.error('Logout failed:', error);
      navigate('/');
    }
  };
  
  const handleConnectChannel = () => {
    // Start Composio OAuth flow
    api.post('/youtube/oauth/start', {})
      .then(response => {
        // Redirect to Composio authorization URL
        window.location.href = response.data.authorization_url;
      })
      .catch(error => {
        toast.error('Failed to start YouTube connection');
        console.error('YouTube OAuth error:', error);
      });
  };
  
  const handleCreateVideo = async () => {
    if (!videoPrompt.trim()) {
      toast.error('Please enter a video prompt');
      return;
    }
    
    try {
      const response = await api.post('/videos/create', {
        prompt: videoPrompt,
        video_length: videoLength,
        voice_style: voiceStyle,
        visual_style: visualStyle
      });
      
      toast.success('Video generation started!');
      setVideoPrompt('');
      navigate('/library');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create video');
    }
  };
  
  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0c] flex items-center justify-center">
        <div className="animate-spin w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full"></div>
      </div>
    );
  }
  
  return (
    <div className="flex h-screen overflow-hidden bg-[#0a0a0c]" data-testid="dashboard">
      {/* Sidebar */}
      <aside className={`fixed inset-y-0 left-0 z-50 w-64 bg-zinc-950 border-r border-zinc-800 transform transition-transform duration-300 lg:translate-x-0 ${
        sidebarOpen ? 'translate-x-0' : '-translate-x-full'
      }`}>
        <div className="flex flex-col h-full">
          <div className="p-6 border-b border-zinc-800">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-md bg-gradient-primary flex items-center justify-center text-white">
                <PlayCircle className="w-5 h-5" />
              </div>
              <span className="font-bold tracking-tighter text-lg text-white">VIDMATIC</span>
            </div>
          </div>
          
          <nav className="flex-1 p-4 space-y-2">
            <NavItem icon={<Sparkles />} label="Dashboard" active onClick={() => navigate('/dashboard')} />
            <NavItem icon={<Video />} label="My Videos" onClick={() => navigate('/library')} />
            <NavItem icon={<BarChart3 />} label="Analytics" onClick={() => navigate('/analytics')} />
            <NavItem icon={<CreditCard />} label="Billing" onClick={() => navigate('/billing')} />
            <NavItem icon={<SettingsIcon />} label="Settings" onClick={() => navigate('/settings')} />
            {user?.role === 'admin' && (
              <NavItem icon={<Shield />} label="Admin" onClick={() => navigate('/admin')} />
            )}
          </nav>
          
          <div className="p-4 border-t border-zinc-800">
            <div className="flex items-center gap-3 mb-4">
              <img 
                src={user?.picture || 'https://via.placeholder.com/40'} 
                alt={user?.name} 
                className="w-10 h-10 rounded-full"
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate">{user?.name}</p>
                <p className="text-xs text-zinc-400 truncate">{user?.email}</p>
              </div>
            </div>
            <Button 
              onClick={handleLogout}
              variant="ghost" 
              className="w-full justify-start text-zinc-400 hover:text-white hover:bg-zinc-800"
              data-testid="logout-btn"
            >
              <LogOut className="w-4 h-4 mr-2" />
              Logout
            </Button>
          </div>
        </div>
      </aside>
      
      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 lg:ml-64">
        {/* Mobile Header */}
        <div className="lg:hidden flex items-center justify-between p-4 border-b border-zinc-800 bg-zinc-950">
          <button onClick={() => setSidebarOpen(!sidebarOpen)}>
            {sidebarOpen ? <X className="w-6 h-6 text-white" /> : <Menu className="w-6 h-6 text-white" />}
          </button>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-gradient-primary flex items-center justify-center text-white">
              <PlayCircle className="w-4 h-4" />
            </div>
            <span className="font-bold text-white">VIDMATIC</span>
          </div>
          <div className="w-6"></div>
        </div>
        
        {/* Topbar */}
        <div className="hidden lg:flex items-center justify-between p-6 border-b border-zinc-800 bg-zinc-950">
          <div>
            <h1 className="text-2xl font-semibold text-white">Dashboard</h1>
            <p className="text-sm text-zinc-400">Create amazing YouTube videos with AI</p>
          </div>
          <div className="flex items-center gap-4">
            <div className="glass-card px-4 py-2 rounded-lg">
              <p className="text-xs text-zinc-400">Video Credits</p>
              <p className="text-lg font-semibold text-white">{user?.video_credits + user?.free_video_credits || 0}</p>
            </div>
          </div>
        </div>
        
        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 md:p-8">
          <div className="max-w-5xl mx-auto">
            {/* Stats Row */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
              <StatCard icon={<Video />} label="Videos Generated" value={stats.videos} color="indigo" />
              <StatCard icon={<Upload />} label="Published" value={stats.published} color="emerald" />
              <StatCard icon={<Eye />} label="Total Views" value={stats.views} color="orange" />
              <StatCard icon={<Youtube />} label="Channels" value={stats.channels} color="red" />
            </div>
            
            {/* Wizard Card */}
            <div className="glass-card rounded-2xl border border-zinc-800 overflow-hidden shadow-xl">
              {/* Stepper Header */}
              <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800/60 bg-zinc-900/30 overflow-x-auto">
                <div className="flex items-center min-w-max">
                  <StepIndicator num={1} label="Connect" active={currentStep === 1} onClick={() => setCurrentStep(1)} />
                  <div className="w-12 md:w-24 h-px bg-zinc-800 mx-4"></div>
                  <StepIndicator num={2} label="Create" active={currentStep === 2} onClick={() => setCurrentStep(2)} />
                  <div className="w-12 md:w-24 h-px bg-zinc-800 mx-4"></div>
                  <StepIndicator num={3} label="Edit & SEO" active={currentStep === 3} onClick={() => setCurrentStep(3)} />
                  <div className="w-12 md:w-24 h-px bg-zinc-800 mx-4"></div>
                  <StepIndicator num={4} label="Publish" active={currentStep === 4} onClick={() => setCurrentStep(4)} />
                </div>
              </div>
              
              {/* Wizard Content */}
              <div className="p-6 md:p-8 min-h-[400px]">
                {currentStep === 1 && (
                  <div className="max-w-xl mx-auto text-center fade-in" data-testid="step-connect">
                    <div className="w-16 h-16 bg-zinc-900 rounded-2xl flex items-center justify-center mx-auto mb-6 border border-zinc-800 shadow-inner">
                      <Youtube className="w-8 h-8 text-red-500" />
                    </div>
                    <h3 className="text-xl font-semibold tracking-tight text-white mb-2">Connect Your Channel</h3>
                    <p className="text-sm text-zinc-400 mb-8">Link your YouTube account via Google OAuth to enable automatic uploading and scheduling.</p>
                    
                    {channels.length > 0 && (
                      <div className="space-y-4 text-left mb-6">
                        {channels.map(channel => (
                          <div key={channel.channel_id} className="p-4 rounded-xl border border-emerald-600/40 bg-gradient-to-r from-emerald-950/50 to-zinc-900/50 shadow-lg">
                            <div className="flex items-start gap-4">
                              <img 
                                src={channel.channel_avatar || 'https://www.youtube.com/img/desktop/yt_1200.png'} 
                                alt={channel.channel_name} 
                                className="w-14 h-14 rounded-full object-cover border-2 border-emerald-500/50 shadow-md"
                                onError={(e) => {
                                  e.target.src = 'https://www.youtube.com/img/desktop/yt_1200.png';
                                }}
                              />
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center justify-between mb-1">
                                  <h4 className="text-base font-semibold text-white truncate">{channel.channel_name}</h4>
                                  <span className="flex items-center gap-1 text-xs font-medium text-emerald-400 bg-emerald-500/20 px-2 py-1 rounded-full">
                                    <CheckCircle className="w-3 h-3" /> Connected
                                  </span>
                                </div>
                                {channel.custom_url && (
                                  <p className="text-xs text-zinc-400 mb-2">{channel.custom_url}</p>
                                )}
                                <div className="flex items-center gap-4 mt-2">
                                  <div className="text-center">
                                    <p className="text-lg font-bold text-white">{channel.subscriber_count?.toLocaleString() || 0}</p>
                                    <p className="text-xs text-zinc-500">Subscribers</p>
                                  </div>
                                  <div className="w-px h-8 bg-zinc-700"></div>
                                  <div className="text-center">
                                    <p className="text-lg font-bold text-white">{channel.video_count?.toLocaleString() || 0}</p>
                                    <p className="text-xs text-zinc-500">Videos</p>
                                  </div>
                                  <div className="w-px h-8 bg-zinc-700"></div>
                                  <div className="text-center">
                                    <p className="text-lg font-bold text-white">{channel.view_count?.toLocaleString() || 0}</p>
                                    <p className="text-xs text-zinc-500">Views</p>
                                  </div>
                                </div>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    
                    <Button 
                      onClick={handleConnectChannel}
                      variant={channels.length > 0 ? "outline" : "default"}
                      className={channels.length > 0 
                        ? "w-full border-zinc-600 text-zinc-300 hover:bg-zinc-800 font-medium py-3 rounded-xl" 
                        : "w-full bg-zinc-100 hover:bg-white text-zinc-900 font-medium py-3 rounded-xl"
                      }
                      data-testid="connect-youtube-btn"
                    >
                      {channels.length > 0 ? 'Connect Another Channel' : 'Connect New Channel'}
                    </Button>
                    
                    {channels.length > 0 && (
                      <div className="mt-8 flex justify-end">
                        <Button 
                          onClick={() => setCurrentStep(2)}
                          className="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-2 rounded-lg"
                        >
                          Continue to Create Video <ArrowRight className="w-4 h-4 ml-2" />
                        </Button>
                      </div>
                    )}
                    
                    {channels.length === 0 && (
                      <div className="mt-8 flex justify-end">
                        <Button 
                          onClick={() => setCurrentStep(2)}
                          variant="ghost"
                          className="text-zinc-400 hover:text-white"
                        >
                          Skip for now <ArrowRight className="w-4 h-4 ml-2" />
                        </Button>
                      </div>
                    )}
                  </div>
                )}
                
                {currentStep === 2 && (
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 fade-in" data-testid="step-create">
                    <div className="lg:col-span-2 space-y-5">
                      <div>
                        <label className="block text-sm font-medium text-white mb-2">What is your video about?</label>
                        <Textarea 
                          rows={4}
                          placeholder="e.g., Explain the history of artificial intelligence from the 1950s to modern LLMs, focusing on key breakthroughs..."
                          value={videoPrompt}
                          onChange={(e) => setVideoPrompt(e.target.value)}
                          className="w-full bg-zinc-900 border border-zinc-800 rounded-xl text-white"
                          data-testid="video-prompt-input"
                        />
                      </div>
                      
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-xs font-medium text-zinc-400 mb-1.5">Video Length</label>
                          <Select value={videoLength} onValueChange={setVideoLength}>
                            <SelectTrigger className="w-full bg-zinc-900 border-zinc-800 text-white">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="short">YouTube Short (60s)</SelectItem>
                              <SelectItem value="medium">Medium (5-8 mins)</SelectItem>
                              <SelectItem value="long">Long (10+ mins)</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-zinc-400 mb-1.5">Voiceover Style</label>
                          <Select value={voiceStyle} onValueChange={setVoiceStyle}>
                            <SelectTrigger className="w-full bg-zinc-900 border-zinc-800 text-white">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="professional">Professional</SelectItem>
                              <SelectItem value="engaging">Engaging</SelectItem>
                              <SelectItem value="energetic">Energetic</SelectItem>
                              <SelectItem value="authoritative">Authoritative</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                    </div>
                    
                    <div className="bg-zinc-900/50 rounded-xl p-5 border border-zinc-800 h-fit">
                      <h4 className="text-sm font-medium text-white mb-3 flex items-center gap-2">
                        <Sparkles className="w-4 h-4 text-indigo-400" />
                        AI Preview
                      </h4>
                      <p className="text-xs text-zinc-400 leading-relaxed">
                        Your video will be generated with AI voiceover, stock footage, and automated editing.
                      </p>
                    </div>
                    
                    <div className="lg:col-span-3 flex justify-end gap-3">
                      <Button 
                        onClick={() => setCurrentStep(1)}
                        variant="outline"
                        className="border-zinc-700 text-white hover:bg-zinc-800"
                      >
                        Back
                      </Button>
                      <Button 
                        onClick={handleCreateVideo}
                        className="bg-indigo-600 hover:bg-indigo-500 text-white"
                        data-testid="generate-video-btn"
                      >
                        Generate Video
                      </Button>
                    </div>
                  </div>
                )}
                
                {currentStep === 3 && (
                  <div className="text-center fade-in">
                    <p className="text-zinc-400">This step will be available after video generation</p>
                  </div>
                )}
                
                {currentStep === 4 && (
                  <div className="text-center fade-in">
                    <p className="text-zinc-400">This step will be available after video is ready</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

const NavItem = ({ icon, label, active, onClick }) => (
  <button
    onClick={onClick}
    className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg transition-colors ${
      active ? 'bg-zinc-800 text-white' : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'
    }`}
  >
    <span className="w-5 h-5">{icon}</span>
    <span className="text-sm font-medium">{label}</span>
  </button>
);

const StatCard = ({ icon, label, value, color }) => (
  <div className="glass-card p-4 rounded-xl flex items-center gap-4">
    <div className={`w-10 h-10 rounded-lg bg-${color}-500/10 flex items-center justify-center text-${color}-400`}>
      {icon}
    </div>
    <div>
      <p className="text-xs text-zinc-400 font-medium">{label}</p>
      <p className="text-xl font-semibold text-white">{value}</p>
    </div>
  </div>
);

const StepIndicator = ({ num, label, active, onClick }) => (
  <div className="wizard-step flex items-center gap-2 cursor-pointer" onClick={onClick}>
    <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${
      active 
        ? 'bg-indigo-500 text-white ring-4 ring-indigo-500/20' 
        : 'bg-zinc-800 text-zinc-400'
    }`}>
      {num}
    </div>
    <span className={`text-sm font-medium ${
      active ? 'text-white' : 'text-zinc-500'
    }`}>{label}</span>
  </div>
);

export default Dashboard;