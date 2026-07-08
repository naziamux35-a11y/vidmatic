import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import api from '../utils/api';
import { toast } from 'sonner';
import { 
  PlayCircle, Video, Upload, Eye, Youtube, Menu, X, LogOut, 
  BarChart3, CreditCard, Settings as SettingsIcon, Shield, Sparkles, 
  ArrowRight, ArrowLeft, CheckCircle, Calendar, Clock, Loader2,
  Wand2, FileText, Volume2, Image, Tag, Send, RefreshCw, Edit3,
  Play, Pause, Download
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Progress } from '../components/ui/progress';
import { Textarea } from '../components/ui/textarea';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const mediaUrl = (u) => (u && u.startsWith('/') ? `${BACKEND_URL}${u}` : u);

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
  
  // Current video being generated/edited
  const [currentVideo, setCurrentVideo] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationProgress, setGenerationProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  
  // SEO editing state
  const [editedTitle, setEditedTitle] = useState('');
  const [editedDescription, setEditedDescription] = useState('');
  const [editedTags, setEditedTags] = useState([]);
  const [newTag, setNewTag] = useState('');
  const [selectedThumbnail, setSelectedThumbnail] = useState(null);
  
  // Publish state
  const [selectedChannel, setSelectedChannel] = useState(null);
  const [scheduleDate, setScheduleDate] = useState('');
  const [scheduleTime, setScheduleTime] = useState('');
  const [publishNow, setPublishNow] = useState(true);
  const [isPublishing, setIsPublishing] = useState(false);
  const [publishResult, setPublishResult] = useState(null);
  
  // Audio player state
  const [isPlaying, setIsPlaying] = useState(false);
  const audioRef = useRef(null);
  
  // Polling interval ref
  const pollIntervalRef = useRef(null);

  useEffect(() => {
    if (location.state?.user) return;
    
    const checkAuth = async () => {
      try {
        const response = await api.get('/auth/me');
        setUser(response.data);
      } catch (error) {
        navigate('/auth');
      } finally {
        setLoading(false);
      }
    };
    
    checkAuth();
  }, [navigate, location.state]);

  useEffect(() => {
    if (user) {
      fetchChannels();
      fetchUserVideos();
    }
  }, [user]);
  
  // Handle YouTube OAuth callback results from URL params
  useEffect(() => {
    const searchParams = new URLSearchParams(location.search);
    const youtubeConnected = searchParams.get('youtube_connected');
    const youtubeError = searchParams.get('youtube_error');
    
    if (youtubeConnected === 'true') {
      toast.success('YouTube channel connected successfully!');
      fetchChannels();
      window.history.replaceState({}, document.title, '/dashboard');
    }
    
    if (youtubeError) {
      toast.error(`YouTube connection failed: ${youtubeError.replace(/_/g, ' ')}`);
      window.history.replaceState({}, document.title, '/dashboard');
    }
  }, [location.search]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  // Handle "Edit" from Library
  useEffect(() => {
    const editVideo = location.state?.editVideo;
    if (editVideo?.video_id) {
      api.get(`/videos/${editVideo.video_id}`)
        .then(res => {
          const v = res.data;
          setCurrentVideo(v);
          setEditedTitle(v.title || '');
          setEditedDescription(v.description || '');
          setEditedTags(v.tags || []);
          setSelectedThumbnail(v.selected_thumbnail_url);
          setCurrentStep(3);
        })
        .catch(() => toast.error('Failed to load video'));
      window.history.replaceState({}, document.title, '/dashboard');
    }
  }, [location.state]);
  
  const fetchChannels = async () => {
    try {
      const response = await api.get('/youtube/channels');
      setChannels(response.data);
      setStats(prev => ({ ...prev, channels: response.data.length }));
      if (response.data.length > 0 && !selectedChannel) {
        setSelectedChannel(response.data[0].channel_id);
      }
    } catch (error) {
      console.error('Failed to fetch channels:', error);
    }
  };

  const fetchUserVideos = async () => {
    try {
      const response = await api.get('/videos/');
      const videos = response.data;
      const published = videos.filter(v => v.status === 'published').length;
      setStats(prev => ({ ...prev, videos: videos.length, published }));
    } catch (error) {
      console.error('Failed to fetch videos:', error);
    }
  };

  const handleConnectChannel = () => {
    api.post('/youtube/oauth/start', {})
      .then(response => {
        window.location.href = response.data.authorization_url;
      })
      .catch(error => {
        toast.error('Failed to start YouTube connection');
        console.error('YouTube OAuth error:', error);
      });
  };

  const handleLogout = async () => {
    try {
      await api.post('/auth/logout');
      navigate('/');
    } catch (error) {
      console.error('Logout error:', error);
      navigate('/');
    }
  };

  const pollVideoProgress = async (videoId) => {
    try {
      const response = await api.get(`/videos/${videoId}/progress`);
      const { status, progress, progress_message, error_message } = response.data;
      
      setGenerationProgress(progress || 0);
      setProgressMessage(progress_message || 'Processing...');
      
      if (status === 'ready') {
        // Video is complete
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
        setIsGenerating(false);
        
        // Fetch full video details
        const videoResponse = await api.get(`/videos/${videoId}`);
        setCurrentVideo(videoResponse.data);
        
        // Pre-populate SEO fields
        setEditedTitle(videoResponse.data.title || '');
        setEditedDescription(videoResponse.data.description || '');
        setEditedTags(videoResponse.data.tags || []);
        setSelectedThumbnail(videoResponse.data.selected_thumbnail_url);
        
        toast.success('Video generated successfully!');
        setCurrentStep(3); // Move to Edit & SEO step
      } else if (status === 'failed') {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
        setIsGenerating(false);
        toast.error(`Video generation failed: ${error_message || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error polling progress:', error);
    }
  };

  const handleGenerateVideo = async () => {
    if (!videoPrompt.trim()) {
      toast.error('Please enter a video topic or prompt');
      return;
    }

    setIsGenerating(true);
    setGenerationProgress(0);
    setProgressMessage('Starting video generation...');
    
    try {
      const response = await api.post('/videos/create', {
        prompt: videoPrompt,
        video_length: videoLength,
        voice_style: voiceStyle,
        visual_style: visualStyle,
        channel_id: selectedChannel
      });
      
      const { video_id } = response.data;
      toast.success('Video generation started!');
      
      // Start polling for progress
      pollIntervalRef.current = setInterval(() => {
        pollVideoProgress(video_id);
      }, 2000);
      
    } catch (error) {
      setIsGenerating(false);
      const message = error.response?.data?.detail || 'Failed to start video generation';
      toast.error(message);
    }
  };

  const handleSaveSEO = async () => {
    if (!currentVideo) return;
    
    try {
      await api.patch(`/videos/${currentVideo.video_id}`, {
        title: editedTitle,
        description: editedDescription,
        tags: editedTags,
        selected_thumbnail_url: selectedThumbnail
      });
      
      setCurrentVideo(prev => ({
        ...prev,
        title: editedTitle,
        description: editedDescription,
        tags: editedTags,
        selected_thumbnail_url: selectedThumbnail
      }));
      
      toast.success('Changes saved!');
    } catch (error) {
      toast.error('Failed to save changes');
    }
  };

  const handleAddTag = () => {
    if (newTag.trim() && !editedTags.includes(newTag.trim())) {
      setEditedTags([...editedTags, newTag.trim()]);
      setNewTag('');
    }
  };

  const handleRemoveTag = (tagToRemove) => {
    setEditedTags(editedTags.filter(tag => tag !== tagToRemove));
  };

  const handlePublish = async () => {
    if (!currentVideo || !selectedChannel) {
      toast.error('Please select a channel to publish to');
      return;
    }
    if (!publishNow && (!scheduleDate || !scheduleTime)) {
      toast.error('Please pick a date and time for scheduling');
      return;
    }

    try {
      const publishData = {
        channel_id: selectedChannel,
        publish_now: publishNow
      };
      if (!publishNow) {
        publishData.scheduled_at = `${scheduleDate}T${scheduleTime}:00Z`;
      }

      setIsPublishing(true);
      const response = await api.post(`/videos/${currentVideo.video_id}/publish`, publishData);
      toast.success(response.data.message);

      // Poll until upload to YouTube completes
      pollIntervalRef.current = setInterval(async () => {
        try {
          const res = await api.get(`/videos/${currentVideo.video_id}`);
          const v = res.data;
          if (v.status === 'published' || v.status === 'scheduled') {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
            setIsPublishing(false);
            setPublishResult(v);
            fetchUserVideos();
          } else if (v.status === 'ready' && v.publish_error) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
            setIsPublishing(false);
            toast.error(`YouTube upload failed: ${v.publish_error}`);
          }
        } catch (e) {
          console.error('Publish poll error:', e);
        }
      }, 4000);
    } catch (error) {
      setIsPublishing(false);
      const message = error.response?.data?.detail || 'Failed to publish video';
      toast.error(message);
    }
  };

  const resetWizard = () => {
    setCurrentVideo(null);
    setPublishResult(null);
    setVideoPrompt('');
    setEditedTitle('');
    setEditedDescription('');
    setEditedTags([]);
    setSelectedThumbnail(null);
    setCurrentStep(1);
    fetchUserVideos();
  };

  const toggleAudio = () => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
      } else {
        audioRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mx-auto mb-4" />
          <p className="text-zinc-400">Loading...</p>
        </div>
      </div>
    );
  }

  const steps = [
    { number: 1, title: 'Connect', icon: Youtube },
    { number: 2, title: 'Create', icon: Wand2 },
    { number: 3, title: 'Edit & SEO', icon: Edit3 },
    { number: 4, title: 'Publish', icon: Send }
  ];

  return (
    <div className="min-h-screen bg-zinc-950 text-white flex">
      {/* Sidebar */}
      <aside className={`fixed lg:static inset-y-0 left-0 z-50 w-64 bg-zinc-900 border-r border-zinc-800 transform ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0 transition-transform duration-200`}>
        <div className="flex flex-col h-full">
          <div className="p-4 border-b border-zinc-800">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-white" />
              </div>
              <span className="text-lg font-bold">Vidmatic</span>
            </div>
          </div>
          
          <nav className="flex-1 p-4 space-y-2">
            <button 
              onClick={() => navigate('/dashboard')}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-lg bg-indigo-600/20 text-indigo-400 border border-indigo-600/30"
            >
              <Video className="w-5 h-5" />
              <span className="font-medium">Create Video</span>
            </button>
            
            <button 
              onClick={() => navigate('/library')}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-zinc-400 hover:bg-zinc-800 hover:text-white transition-colors"
            >
              <PlayCircle className="w-5 h-5" />
              <span>Video Library</span>
            </button>
            
            <button 
              onClick={() => navigate('/analytics')}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-zinc-400 hover:bg-zinc-800 hover:text-white transition-colors"
            >
              <BarChart3 className="w-5 h-5" />
              <span>Analytics</span>
            </button>
            
            <button 
              onClick={() => navigate('/billing')}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-zinc-400 hover:bg-zinc-800 hover:text-white transition-colors"
            >
              <CreditCard className="w-5 h-5" />
              <span>Billing</span>
            </button>
            
            <button 
              onClick={() => navigate('/settings')}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-zinc-400 hover:bg-zinc-800 hover:text-white transition-colors"
            >
              <SettingsIcon className="w-5 h-5" />
              <span>Settings</span>
            </button>
          </nav>
          
          {/* User info */}
          <div className="p-4 border-t border-zinc-800">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-sm font-bold">
                {user?.name?.charAt(0) || 'U'}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{user?.name || 'User'}</p>
                <p className="text-xs text-zinc-500 truncate">{user?.email}</p>
              </div>
            </div>
            <button 
              onClick={handleLogout}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-zinc-400 hover:bg-zinc-800 hover:text-white transition-colors text-sm"
            >
              <LogOut className="w-4 h-4" />
              <span>Sign Out</span>
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 min-h-screen">
        {/* Mobile Header */}
        <header className="lg:hidden sticky top-0 z-40 bg-zinc-900/80 backdrop-blur-xl border-b border-zinc-800 p-4">
          <div className="flex items-center justify-between">
            <button onClick={() => setSidebarOpen(!sidebarOpen)} className="p-2 hover:bg-zinc-800 rounded-lg">
              {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
            <span className="font-bold">Vidmatic</span>
            <div className="w-10" />
          </div>
        </header>

        <div className="p-6 lg:p-8 max-w-6xl mx-auto">
          {/* Steps Progress */}
          <div className="mb-8">
            <div className="flex items-center justify-between mb-4">
              {steps.map((step, index) => (
                <React.Fragment key={step.number}>
                  <button
                    onClick={() => {
                      if (step.number === 1) setCurrentStep(1);
                      else if (step.number === 2) setCurrentStep(2);  // Allow access to Create without channel
                      else if (step.number === 3 && currentVideo?.status === 'ready') setCurrentStep(3);
                      else if (step.number === 4 && currentVideo?.status === 'ready') setCurrentStep(4);
                    }}
                    className={`flex flex-col items-center gap-2 transition-all ${
                      currentStep >= step.number ? 'opacity-100' : 'opacity-40'
                    }`}
                  >
                    <div className={`w-12 h-12 rounded-full flex items-center justify-center transition-all ${
                      currentStep === step.number 
                        ? 'bg-indigo-600 text-white scale-110' 
                        : currentStep > step.number 
                          ? 'bg-emerald-600 text-white' 
                          : 'bg-zinc-800 text-zinc-400'
                    }`}>
                      {currentStep > step.number ? (
                        <CheckCircle className="w-6 h-6" />
                      ) : (
                        <step.icon className="w-6 h-6" />
                      )}
                    </div>
                    <span className={`text-sm font-medium ${currentStep === step.number ? 'text-white' : 'text-zinc-500'}`}>
                      {step.title}
                    </span>
                  </button>
                  {index < steps.length - 1 && (
                    <div className={`flex-1 h-1 mx-2 rounded ${currentStep > step.number ? 'bg-emerald-600' : 'bg-zinc-800'}`} />
                  )}
                </React.Fragment>
              ))}
            </div>
          </div>

          {/* Step Content */}
          <div className="bg-zinc-900 rounded-2xl border border-zinc-800 p-6 lg:p-8">
            
            {/* ===== STEP 1: CONNECT ===== */}
            {currentStep === 1 && (
              <div className="text-center max-w-xl mx-auto">
                <div className="w-16 h-16 rounded-full bg-red-600/20 flex items-center justify-center mx-auto mb-6">
                  <Youtube className="w-8 h-8 text-red-500" />
                </div>
                <h2 className="text-2xl font-bold mb-2">Connect Your YouTube Channel</h2>
                <p className="text-zinc-400 mb-8">Link your YouTube account to enable automatic video publishing and scheduling.</p>
                
                {channels.length > 0 && (
                  <div className="space-y-4 text-left mb-6">
                    {channels.map(channel => (
                      <div key={channel.channel_id} className="p-4 rounded-xl border border-emerald-600/40 bg-gradient-to-r from-emerald-950/50 to-zinc-900/50">
                        <div className="flex items-start gap-4">
                          <img 
                            src={channel.channel_avatar || 'https://www.youtube.com/img/desktop/yt_1200.png'} 
                            alt={channel.channel_name} 
                            className="w-14 h-14 rounded-full object-cover border-2 border-emerald-500/50"
                            onError={(e) => { e.target.src = 'https://www.youtube.com/img/desktop/yt_1200.png'; }}
                          />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between mb-1">
                              <h4 className="text-base font-semibold truncate">{channel.channel_name}</h4>
                              <span className="flex items-center gap-1 text-xs font-medium text-emerald-400 bg-emerald-500/20 px-2 py-1 rounded-full">
                                <CheckCircle className="w-3 h-3" /> Connected
                              </span>
                            </div>
                            {channel.custom_url && <p className="text-xs text-zinc-400 mb-2">{channel.custom_url}</p>}
                            <div className="flex items-center gap-4 mt-2">
                              <div className="text-center">
                                <p className="text-lg font-bold">{channel.subscriber_count?.toLocaleString() || 0}</p>
                                <p className="text-xs text-zinc-500">Subscribers</p>
                              </div>
                              <div className="w-px h-8 bg-zinc-700"></div>
                              <div className="text-center">
                                <p className="text-lg font-bold">{channel.video_count?.toLocaleString() || 0}</p>
                                <p className="text-xs text-zinc-500">Videos</p>
                              </div>
                              <div className="w-px h-8 bg-zinc-700"></div>
                              <div className="text-center">
                                <p className="text-lg font-bold">{channel.view_count?.toLocaleString() || 0}</p>
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
                    ? "w-full border-zinc-600 text-zinc-300 hover:bg-zinc-800 py-3 rounded-xl mb-4" 
                    : "w-full bg-white hover:bg-zinc-100 text-zinc-900 py-3 rounded-xl mb-4"
                  }
                >
                  {channels.length > 0 ? 'Connect Another Channel' : 'Connect YouTube Channel'}
                </Button>
                
                <Button onClick={() => setCurrentStep(2)} className="w-full bg-indigo-600 hover:bg-indigo-500 py-3 rounded-xl">
                  {channels.length > 0 ? 'Continue to Create Video' : 'Skip & Create Video'} <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
                
                {channels.length === 0 && (
                  <p className="text-xs text-zinc-500 mt-2 text-center">
                    You can connect a channel later when you're ready to publish
                  </p>
                )}
              </div>
            )}

            {/* ===== STEP 2: CREATE ===== */}
            {currentStep === 2 && !isGenerating && (
              <div className="fade-in">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-12 h-12 rounded-full bg-indigo-600/20 flex items-center justify-center">
                    <Wand2 className="w-6 h-6 text-indigo-400" />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold">Create Your Video</h2>
                    <p className="text-zinc-400 text-sm">Tell us what your video is about and we'll generate everything</p>
                  </div>
                </div>
                
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                  <div className="lg:col-span-2 space-y-5">
                    <div>
                      <label className="block text-sm font-medium mb-2">Video Topic / Prompt</label>
                      <Textarea 
                        rows={4}
                        placeholder="e.g., Explain the history of artificial intelligence from the 1950s to modern LLMs, focusing on key breakthroughs and how they changed technology..."
                        value={videoPrompt}
                        onChange={(e) => setVideoPrompt(e.target.value)}
                        className="w-full bg-zinc-800 border border-zinc-700 rounded-xl text-white focus:border-indigo-500"
                      />
                      <p className="text-xs text-zinc-500 mt-1">Be specific for better results. Include key points you want covered.</p>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium mb-2">Video Length</label>
                        <Select value={videoLength} onValueChange={setVideoLength}>
                          <SelectTrigger className="bg-zinc-800 border-zinc-700">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent className="bg-zinc-800 border-zinc-700">
                            <SelectItem value="short">Short (~1 min)</SelectItem>
                            <SelectItem value="medium">Medium (2-5 min)</SelectItem>
                            <SelectItem value="long">Long (5-8 min)</SelectItem>
                            <SelectItem value="extended">Extended (10-15 min)</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div>
                        <label className="block text-sm font-medium mb-2">Voice Style</label>
                        <Select value={voiceStyle} onValueChange={setVoiceStyle}>
                          <SelectTrigger className="bg-zinc-800 border-zinc-700">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent className="bg-zinc-800 border-zinc-700">
                            <SelectItem value="professional">Professional</SelectItem>
                            <SelectItem value="engaging">Engaging</SelectItem>
                            <SelectItem value="energetic">Energetic</SelectItem>
                            <SelectItem value="authoritative">Authoritative</SelectItem>
                            <SelectItem value="friendly">Friendly</SelectItem>
                            <SelectItem value="calm">Calm</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  </div>
                  
                  <div className="bg-zinc-800/50 rounded-xl p-5 border border-zinc-700">
                    <h3 className="font-medium mb-4 flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-indigo-400" /> What We'll Generate
                    </h3>
                    <ul className="space-y-3 text-sm text-zinc-400">
                      <li className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-emerald-400" />
                        <span>AI-written video script</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <Volume2 className="w-4 h-4 text-blue-400" />
                        <span>Professional voiceover</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <Video className="w-4 h-4 text-purple-400" />
                        <span>Stock footage & visuals</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <Image className="w-4 h-4 text-pink-400" />
                        <span>Thumbnail options</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <Tag className="w-4 h-4 text-yellow-400" />
                        <span>SEO-optimized metadata</span>
                      </li>
                    </ul>
                    
                    <div className="mt-6 pt-4 border-t border-zinc-700">
                      <p className="text-xs text-zinc-500 mb-2">Credits remaining</p>
                      <p className="text-2xl font-bold text-indigo-400">{(user?.video_credits || 0) + (user?.free_video_credits || 0)}</p>
                    </div>
                  </div>
                </div>
                
                <div className="mt-8 flex items-center justify-between">
                  <Button variant="ghost" onClick={() => setCurrentStep(1)} className="text-zinc-400">
                    <ArrowLeft className="w-4 h-4 mr-2" /> Back
                  </Button>
                  <Button 
                    onClick={handleGenerateVideo}
                    disabled={!videoPrompt.trim()}
                    className="bg-indigo-600 hover:bg-indigo-500 px-8 py-3"
                  >
                    <Wand2 className="w-4 h-4 mr-2" /> Generate Video
                  </Button>
                </div>
              </div>
            )}

            {/* ===== STEP 2: GENERATING ===== */}
            {currentStep === 2 && isGenerating && (
              <div className="text-center max-w-lg mx-auto py-12">
                <div className="w-20 h-20 rounded-full bg-indigo-600/20 flex items-center justify-center mx-auto mb-6 animate-pulse">
                  <Loader2 className="w-10 h-10 text-indigo-400 animate-spin" />
                </div>
                <h2 className="text-2xl font-bold mb-2">Generating Your Video</h2>
                <p className="text-zinc-400 mb-8">{progressMessage}</p>
                
                <div className="mb-4">
                  <Progress value={generationProgress} className="h-3 bg-zinc-800" />
                </div>
                <p className="text-sm text-zinc-500">{generationProgress}% complete</p>
                
                <div className="mt-8 grid grid-cols-6 gap-2">
                  {[
                    { label: 'Script', at: 8 },
                    { label: 'Footage', at: 24 },
                    { label: 'Voice', at: 42 },
                    { label: 'Thumbs', at: 64 },
                    { label: 'SEO', at: 76 },
                    { label: 'Render', at: 82 }
                  ].map((step, i, arr) => {
                    const nextAt = arr[i + 1]?.at ?? 100;
                    return (
                      <div key={step.label} className="text-center">
                        <div className={`w-8 h-8 rounded-full mx-auto mb-1 flex items-center justify-center ${
                          generationProgress >= nextAt ? 'bg-emerald-600' : 
                          generationProgress >= step.at ? 'bg-indigo-600 animate-pulse' : 'bg-zinc-800'
                        }`}>
                          {generationProgress >= nextAt ? (
                            <CheckCircle className="w-4 h-4" />
                          ) : (
                            <span className="text-xs">{i + 1}</span>
                          )}
                        </div>
                        <span className="text-xs text-zinc-500">{step.label}</span>
                      </div>
                    );
                  })}
                </div>
                <p className="text-xs text-zinc-600 mt-6">Rendering a full HD video takes a few minutes — feel free to keep this tab open.</p>
              </div>
            )}

            {/* ===== STEP 3: EDIT & SEO ===== */}
            {currentStep === 3 && currentVideo && (
              <div className="fade-in">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-12 h-12 rounded-full bg-purple-600/20 flex items-center justify-center">
                    <Edit3 className="w-6 h-6 text-purple-400" />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold">Edit & Optimize</h2>
                    <p className="text-zinc-400 text-sm">Review your video, edit content, and optimize for search</p>
                  </div>
                </div>
                
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                  {/* Left: Preview */}
                  <div className="space-y-4">
                    {/* Rendered Video Preview */}
                    {currentVideo.video_url && (
                      <div>
                        <div className="flex items-center justify-between mb-3">
                          <label className="text-sm font-medium">Video Preview</label>
                          <Button
                            size="sm"
                            variant="outline"
                            className="border-zinc-600 h-8"
                            onClick={() => {
                              const link = document.createElement('a');
                              link.href = mediaUrl(currentVideo.download_url || currentVideo.video_url);
                              link.download = `${currentVideo.title || currentVideo.video_id}.mp4`;
                              document.body.appendChild(link);
                              link.click();
                              document.body.removeChild(link);
                            }}
                            data-testid="step3-download-btn"
                          >
                            <Download className="w-3 h-3 mr-1" /> Download MP4
                          </Button>
                        </div>
                        <video
                          controls
                          className="w-full aspect-video rounded-xl bg-black border border-zinc-800"
                          src={mediaUrl(currentVideo.video_url)}
                          data-testid="step3-video-player"
                        />
                        {(currentVideo.rendered_duration > 0 || currentVideo.file_size_mb > 0) && (
                          <p className="text-xs text-zinc-500 mt-1">
                            {currentVideo.rendered_duration ? `${Math.floor(currentVideo.rendered_duration / 60)}:${String(Math.round(currentVideo.rendered_duration % 60)).padStart(2, '0')} min` : ''}
                            {currentVideo.file_size_mb ? ` · ${currentVideo.file_size_mb} MB · 1080p HD` : ''}
                          </p>
                        )}
                      </div>
                    )}
                    {/* Thumbnail Selection */}
                    <div>
                      <label className="block text-sm font-medium mb-3">Select Thumbnail</label>
                      <div className="grid grid-cols-3 gap-3">
                        {currentVideo.thumbnail_urls?.map((url, i) => (
                          <button
                            key={i}
                            onClick={() => setSelectedThumbnail(url)}
                            className={`relative rounded-lg overflow-hidden border-2 transition-all ${
                              selectedThumbnail === url ? 'border-indigo-500 scale-105' : 'border-transparent hover:border-zinc-600'
                            }`}
                          >
                            <img src={url} alt={`Thumbnail ${i + 1}`} className="w-full h-20 object-cover" />
                            {selectedThumbnail === url && (
                              <div className="absolute inset-0 bg-indigo-600/30 flex items-center justify-center">
                                <CheckCircle className="w-6 h-6 text-white" />
                              </div>
                            )}
                          </button>
                        ))}
                      </div>
                    </div>
                    
                    {/* Audio Preview */}
                    {currentVideo.voiceover_url && (
                      <div className="bg-zinc-800 rounded-xl p-4">
                        <label className="block text-sm font-medium mb-3 flex items-center gap-2">
                          <Volume2 className="w-4 h-4 text-blue-400" /> Voiceover Preview
                        </label>
                        <div className="flex items-center gap-4">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={toggleAudio}
                            className="border-zinc-600"
                          >
                            {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                          </Button>
                          <div className="flex-1 h-2 bg-zinc-700 rounded-full">
                            <div className="h-full w-1/3 bg-blue-500 rounded-full"></div>
                          </div>
                          <span className="text-xs text-zinc-400">
                            {Math.round(currentVideo.voiceover_duration || 0)} min
                          </span>
                        </div>
                        <audio ref={audioRef} src={mediaUrl(currentVideo.voiceover_url)} onEnded={() => setIsPlaying(false)} />
                      </div>
                    )}
                    
                    {/* Script Preview */}
                    <div className="bg-zinc-800 rounded-xl p-4 max-h-60 overflow-y-auto">
                      <label className="block text-sm font-medium mb-2 flex items-center gap-2">
                        <FileText className="w-4 h-4 text-emerald-400" /> Script Preview
                      </label>
                      <p className="text-sm text-zinc-400 whitespace-pre-wrap">
                        {currentVideo.script?.substring(0, 500)}...
                      </p>
                    </div>
                  </div>
                  
                  {/* Right: SEO */}
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium mb-2">Video Title</label>
                      <Input
                        value={editedTitle}
                        onChange={(e) => setEditedTitle(e.target.value)}
                        placeholder="Enter video title"
                        className="bg-zinc-800 border-zinc-700"
                        maxLength={100}
                      />
                      <p className="text-xs text-zinc-500 mt-1">{editedTitle.length}/100 characters</p>
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium mb-2">Description</label>
                      <Textarea
                        rows={6}
                        value={editedDescription}
                        onChange={(e) => setEditedDescription(e.target.value)}
                        placeholder="Enter video description"
                        className="bg-zinc-800 border-zinc-700"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium mb-2">Tags</label>
                      <div className="flex gap-2 mb-2">
                        <Input
                          value={newTag}
                          onChange={(e) => setNewTag(e.target.value)}
                          onKeyPress={(e) => e.key === 'Enter' && handleAddTag()}
                          placeholder="Add a tag"
                          className="bg-zinc-800 border-zinc-700"
                        />
                        <Button onClick={handleAddTag} variant="outline" className="border-zinc-600">Add</Button>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {editedTags.map((tag, i) => (
                          <span key={i} className="px-3 py-1 bg-zinc-800 rounded-full text-sm flex items-center gap-1">
                            {tag}
                            <button onClick={() => handleRemoveTag(tag)} className="text-zinc-500 hover:text-red-400">×</button>
                          </span>
                        ))}
                      </div>
                    </div>
                    
                    {/* SEO Score */}
                    <div className="bg-gradient-to-r from-emerald-950/50 to-zinc-900 rounded-xl p-4 border border-emerald-700/30">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium">SEO Score</span>
                        <span className="text-2xl font-bold text-emerald-400">{currentVideo.seo_score || 75}/100</span>
                      </div>
                      <Progress value={currentVideo.seo_score || 75} className="h-2 bg-zinc-800" />
                    </div>
                  </div>
                </div>
                
                <div className="mt-8 flex items-center justify-between">
                  <Button variant="ghost" onClick={() => setCurrentStep(2)} className="text-zinc-400">
                    <ArrowLeft className="w-4 h-4 mr-2" /> Back
                  </Button>
                  <div className="flex gap-3">
                    <Button onClick={handleSaveSEO} variant="outline" className="border-zinc-600">
                      Save Changes
                    </Button>
                    <Button onClick={() => setCurrentStep(4)} className="bg-indigo-600 hover:bg-indigo-500 px-8">
                      Continue to Publish <ArrowRight className="w-4 h-4 ml-2" />
                    </Button>
                  </div>
                </div>
              </div>
            )}

            {/* ===== STEP 4: PUBLISHING IN PROGRESS ===== */}
            {currentStep === 4 && isPublishing && (
              <div className="text-center max-w-lg mx-auto py-16" data-testid="publishing-progress">
                <div className="w-20 h-20 rounded-full bg-red-600/20 flex items-center justify-center mx-auto mb-6 animate-pulse">
                  <Youtube className="w-10 h-10 text-red-500" />
                </div>
                <h2 className="text-2xl font-bold mb-2">Uploading to YouTube</h2>
                <p className="text-zinc-400 mb-6">Your HD video is being uploaded to your channel. This can take a few minutes depending on video size.</p>
                <Loader2 className="w-8 h-8 animate-spin text-indigo-400 mx-auto" />
              </div>
            )}

            {/* ===== STEP 4: PUBLISH SUCCESS ===== */}
            {currentStep === 4 && publishResult && !isPublishing && (
              <div className="text-center max-w-lg mx-auto py-12" data-testid="publish-success">
                <div className="w-20 h-20 rounded-full bg-emerald-600/20 flex items-center justify-center mx-auto mb-6">
                  <CheckCircle className="w-10 h-10 text-emerald-400" />
                </div>
                <h2 className="text-2xl font-bold mb-2">
                  {publishResult.status === 'published' ? 'Video Published! 🎉' : 'Video Scheduled! 📅'}
                </h2>
                <p className="text-zinc-400 mb-6">
                  {publishResult.status === 'published'
                    ? 'Your video is now live on YouTube.'
                    : `Uploaded to YouTube as private — it will automatically go public at ${new Date(publishResult.scheduled_at).toLocaleString()}.`}
                </p>
                {publishResult.youtube_url && (
                  <Button
                    onClick={() => window.open(publishResult.youtube_url, '_blank')}
                    className="bg-red-600 hover:bg-red-500 mb-4 w-full py-3"
                    data-testid="view-on-youtube-btn"
                  >
                    <Youtube className="w-4 h-4 mr-2" /> View on YouTube
                  </Button>
                )}
                <div className="flex gap-3">
                  <Button onClick={() => navigate('/library')} variant="outline" className="flex-1 border-zinc-600">
                    Go to Library
                  </Button>
                  <Button onClick={resetWizard} className="flex-1 bg-indigo-600 hover:bg-indigo-500" data-testid="create-another-btn">
                    Create Another Video
                  </Button>
                </div>
              </div>
            )}

            {/* ===== STEP 4: PUBLISH ===== */}
            {currentStep === 4 && currentVideo && !isPublishing && !publishResult && (
              <div className="fade-in">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-12 h-12 rounded-full bg-emerald-600/20 flex items-center justify-center">
                    <Send className="w-6 h-6 text-emerald-400" />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold">Ready to Publish</h2>
                    <p className="text-zinc-400 text-sm">Review your video and publish to YouTube</p>
                  </div>
                </div>
                
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                  {/* Video Summary */}
                  <div className="bg-zinc-800 rounded-xl overflow-hidden">
                    <img 
                      src={selectedThumbnail || currentVideo.selected_thumbnail_url} 
                      alt="Video thumbnail" 
                      className="w-full h-48 object-cover"
                    />
                    <div className="p-4">
                      <h3 className="font-bold text-lg mb-2">{editedTitle || currentVideo.title}</h3>
                      <p className="text-zinc-400 text-sm line-clamp-3">{editedDescription || currentVideo.description}</p>
                      <div className="mt-4 flex flex-wrap gap-2">
                        {(editedTags.length > 0 ? editedTags : currentVideo.tags || []).slice(0, 5).map((tag, i) => (
                          <span key={i} className="px-2 py-1 bg-zinc-700 rounded text-xs">{tag}</span>
                        ))}
                      </div>
                    </div>
                  </div>
                  
                  {/* Publish Options */}
                  <div className="space-y-6">
                    {/* Channel Selection */}
                    <div>
                      <label className="block text-sm font-medium mb-3">Publish to Channel</label>
                      {channels.length === 0 ? (
                        <div className="p-4 rounded-xl border border-yellow-600/40 bg-yellow-950/20 text-center">
                          <Youtube className="w-8 h-8 text-yellow-500 mx-auto mb-2" />
                          <p className="text-sm text-yellow-200 mb-3">No YouTube channel connected</p>
                          <Button 
                            onClick={handleConnectChannel}
                            className="bg-red-600 hover:bg-red-500 text-white"
                          >
                            Connect YouTube Channel
                          </Button>
                        </div>
                      ) : (
                        <div className="space-y-2">
                          {channels.map(channel => (
                            <button
                              key={channel.channel_id}
                              onClick={() => setSelectedChannel(channel.channel_id)}
                              className={`w-full flex items-center gap-3 p-3 rounded-xl border transition-all ${
                                selectedChannel === channel.channel_id 
                                  ? 'border-indigo-500 bg-indigo-600/10' 
                                  : 'border-zinc-700 hover:border-zinc-600'
                              }`}
                            >
                              <img 
                                src={channel.channel_avatar || 'https://www.youtube.com/img/desktop/yt_1200.png'} 
                                alt={channel.channel_name}
                                className="w-10 h-10 rounded-full"
                              />
                              <div className="flex-1 text-left">
                                <p className="font-medium">{channel.channel_name}</p>
                                <p className="text-xs text-zinc-500">{channel.subscriber_count?.toLocaleString()} subscribers</p>
                              </div>
                              {selectedChannel === channel.channel_id && (
                                <CheckCircle className="w-5 h-5 text-indigo-400" />
                              )}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                    
                    {channels.length > 0 && (
                    <>
                    {/* Publish Options */}
                    <div>
                      <label className="block text-sm font-medium mb-3">When to Publish</label>
                      <div className="space-y-3">
                        <button
                          onClick={() => setPublishNow(true)}
                          className={`w-full flex items-center gap-3 p-4 rounded-xl border transition-all ${
                            publishNow ? 'border-emerald-500 bg-emerald-600/10' : 'border-zinc-700 hover:border-zinc-600'
                          }`}
                        >
                          <Send className="w-5 h-5 text-emerald-400" />
                          <div className="flex-1 text-left">
                            <p className="font-medium">Publish Now</p>
                            <p className="text-xs text-zinc-500">Your video will be live immediately</p>
                          </div>
                          {publishNow && <CheckCircle className="w-5 h-5 text-emerald-400" />}
                        </button>
                        
                        <button
                          onClick={() => setPublishNow(false)}
                          className={`w-full flex items-center gap-3 p-4 rounded-xl border transition-all ${
                            !publishNow ? 'border-blue-500 bg-blue-600/10' : 'border-zinc-700 hover:border-zinc-600'
                          }`}
                        >
                          <Calendar className="w-5 h-5 text-blue-400" />
                          <div className="flex-1 text-left">
                            <p className="font-medium">Schedule for Later</p>
                            <p className="text-xs text-zinc-500">Choose a specific date and time</p>
                          </div>
                          {!publishNow && <CheckCircle className="w-5 h-5 text-blue-400" />}
                        </button>
                        
                        {!publishNow && (
                          <div className="grid grid-cols-2 gap-3 mt-3">
                            <Input
                              type="date"
                              value={scheduleDate}
                              onChange={(e) => setScheduleDate(e.target.value)}
                              className="bg-zinc-800 border-zinc-700"
                            />
                            <Input
                              type="time"
                              value={scheduleTime}
                              onChange={(e) => setScheduleTime(e.target.value)}
                              className="bg-zinc-800 border-zinc-700"
                            />
                          </div>
                        )}
                      </div>
                    </div>
                    </>
                    )}
                  </div>
                </div>
                
                <div className="mt-8 flex items-center justify-between">
                  <Button variant="ghost" onClick={() => setCurrentStep(3)} className="text-zinc-400">
                    <ArrowLeft className="w-4 h-4 mr-2" /> Back to Edit
                  </Button>
                  {channels.length > 0 ? (
                    <Button 
                      onClick={handlePublish}
                      disabled={!selectedChannel}
                      className="bg-emerald-600 hover:bg-emerald-500 px-8 py-3"
                    >
                      {publishNow ? (
                        <><Send className="w-4 h-4 mr-2" /> Publish Now</>
                      ) : (
                        <><Calendar className="w-4 h-4 mr-2" /> Schedule Video</>
                      )}
                    </Button>
                  ) : (
                    <Button 
                      onClick={() => navigate('/library')}
                      variant="outline"
                      className="border-zinc-600"
                    >
                      Save to Library
                    </Button>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 lg:hidden" 
          onClick={() => setSidebarOpen(false)}
        />
      )}
    </div>
  );
};

export default Dashboard;
