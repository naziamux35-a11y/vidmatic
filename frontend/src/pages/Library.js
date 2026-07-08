import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../utils/api';
import { toast } from 'sonner';
import { 
  Video, PlayCircle, Clock, Eye, Calendar, Trash2, Edit3, 
  Download, Youtube, Loader2, ArrowLeft, Filter, Search,
  CheckCircle, AlertCircle, Clock3, Send, MoreVertical, X
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const Library = () => {
  const navigate = useNavigate();
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [playingVideo, setPlayingVideo] = useState(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(null);

  const handleDownload = (video) => {
    if (!video.download_url) {
      toast.info('Video file not available yet');
      return;
    }
    const link = document.createElement('a');
    link.href = `${BACKEND_URL}${video.download_url}`;
    link.download = `${video.title || video.video_id}.mp4`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast.success('Download started');
  };

  useEffect(() => {
    fetchVideos();
  }, []);

  const fetchVideos = async () => {
    try {
      const response = await api.get('/videos/');
      setVideos(response.data);
    } catch (error) {
      console.error('Failed to fetch videos:', error);
      if (error.response?.status === 401) {
        navigate('/auth');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteVideo = async (videoId) => {
    try {
      await api.delete(`/videos/${videoId}`);
      toast.success('Video deleted');
      setVideos(videos.filter(v => v.video_id !== videoId));
      setShowDeleteConfirm(null);
    } catch (error) {
      toast.error('Failed to delete video');
    }
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      pending: { color: 'bg-yellow-500/20 text-yellow-400', icon: Clock3, label: 'Pending' },
      generating_script: { color: 'bg-blue-500/20 text-blue-400', icon: Loader2, label: 'Generating Script' },
      generating_video: { color: 'bg-blue-500/20 text-blue-400', icon: Loader2, label: 'Creating Video' },
      generating_voiceover: { color: 'bg-purple-500/20 text-purple-400', icon: Loader2, label: 'Generating Voice' },
      generating_thumbnail: { color: 'bg-pink-500/20 text-pink-400', icon: Loader2, label: 'Creating Thumbnails' },
      rendering: { color: 'bg-orange-500/20 text-orange-400', icon: Loader2, label: 'Rendering HD Video' },
      ready: { color: 'bg-emerald-500/20 text-emerald-400', icon: CheckCircle, label: 'Ready' },
      publishing: { color: 'bg-red-500/20 text-red-400', icon: Loader2, label: 'Uploading to YouTube' },
      scheduled: { color: 'bg-indigo-500/20 text-indigo-400', icon: Calendar, label: 'Scheduled' },
      published: { color: 'bg-green-500/20 text-green-400', icon: Youtube, label: 'Published' },
      failed: { color: 'bg-red-500/20 text-red-400', icon: AlertCircle, label: 'Failed' }
    };
    
    const config = statusConfig[status] || statusConfig.pending;
    const Icon = config.icon;
    
    return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${config.color}`}>
        <Icon className={`w-3 h-3 ${(status.includes('generating') || status === 'rendering' || status === 'publishing') ? 'animate-spin' : ''}`} />
        {config.label}
      </span>
    );
  };

  const filteredVideos = videos.filter(video => {
    const matchesFilter = filter === 'all' || video.status === filter;
    const matchesSearch = !searchQuery || 
      video.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      video.prompt?.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
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
      {/* Header */}
      <header className="border-b border-zinc-800 bg-zinc-900/50 backdrop-blur-xl sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button 
                onClick={() => navigate('/dashboard')}
                className="p-2 hover:bg-zinc-800 rounded-lg transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div>
                <h1 className="text-xl font-bold">Video Library</h1>
                <p className="text-sm text-zinc-400">{videos.length} videos</p>
              </div>
            </div>
            <Button 
              onClick={() => navigate('/dashboard')}
              className="bg-indigo-600 hover:bg-indigo-500"
            >
              <Video className="w-4 h-4 mr-2" /> Create New Video
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4 mb-8">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <Input
              placeholder="Search videos..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 bg-zinc-900 border-zinc-800"
            />
          </div>
          <div className="flex gap-2 flex-wrap">
            {['all', 'ready', 'scheduled', 'published', 'failed'].map(status => (
              <button
                key={status}
                onClick={() => setFilter(status)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  filter === status 
                    ? 'bg-indigo-600 text-white' 
                    : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'
                }`}
              >
                {status.charAt(0).toUpperCase() + status.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Videos Grid */}
        {filteredVideos.length === 0 ? (
          <div className="text-center py-16">
            <Video className="w-16 h-16 text-zinc-700 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-zinc-400 mb-2">No videos found</h3>
            <p className="text-zinc-500 mb-6">
              {filter !== 'all' 
                ? `No ${filter} videos yet` 
                : "Start creating your first AI-powered video"}
            </p>
            <Button onClick={() => navigate('/dashboard')} className="bg-indigo-600 hover:bg-indigo-500">
              Create Your First Video
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredVideos.map(video => (
              <div 
                key={video.video_id}
                className="bg-zinc-900 rounded-xl border border-zinc-800 overflow-hidden hover:border-zinc-700 transition-all group"
              >
                {/* Thumbnail */}
                <div
                  className={`relative aspect-video bg-zinc-800 ${(video.status === 'ready' || video.status === 'published' || video.status === 'scheduled') && video.video_url ? 'cursor-pointer' : ''}`}
                  onClick={() => {
                    if ((video.status === 'ready' || video.status === 'published' || video.status === 'scheduled') && video.video_url) {
                      setPlayingVideo(video);
                    }
                  }}
                  data-testid={`video-card-thumb-${video.video_id}`}
                >
                  {video.selected_thumbnail_url ? (
                    <img 
                      src={video.selected_thumbnail_url} 
                      alt={video.title || 'Video thumbnail'}
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        e.target.src = 'https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=400';
                      }}
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Video className="w-12 h-12 text-zinc-700" />
                    </div>
                  )}
                  
                  {/* Status Badge */}
                  <div className="absolute top-3 left-3">
                    {getStatusBadge(video.status)}
                  </div>
                  
                  {/* Progress Overlay for generating videos */}
                  {(video.status?.includes('generating') || video.status === 'rendering' || video.status === 'pending') && (
                    <div className="absolute inset-0 bg-black/60 flex flex-col items-center justify-center">
                      <Loader2 className="w-8 h-8 text-indigo-400 animate-spin mb-2" />
                      <p className="text-sm text-white">{video.progress || 0}% Complete</p>
                      <p className="text-xs text-zinc-400 mt-1">{video.progress_message}</p>
                    </div>
                  )}
                  
                  {/* Play Button Overlay */}
                  {video.status === 'ready' && (
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                      <button className="w-14 h-14 rounded-full bg-white/20 backdrop-blur flex items-center justify-center hover:bg-white/30 transition-colors">
                        <PlayCircle className="w-8 h-8 text-white" />
                      </button>
                    </div>
                  )}
                </div>
                
                {/* Content */}
                <div className="p-4">
                  <h3 className="font-semibold text-white mb-1 line-clamp-2">
                    {video.title || video.prompt?.substring(0, 50) || 'Untitled Video'}
                  </h3>
                  <p className="text-sm text-zinc-500 line-clamp-2 mb-3">
                    {video.prompt?.substring(0, 80)}...
                  </p>
                  
                  {/* Meta Info */}
                  <div className="flex items-center gap-4 text-xs text-zinc-500 mb-4">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {video.video_length || 'medium'}
                    </span>
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3 h-3" />
                      {formatDate(video.created_at)}
                    </span>
                  </div>
                  
                  {/* SEO Score */}
                  {video.seo_score > 0 && (
                    <div className="mb-4">
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-zinc-400">SEO Score</span>
                        <span className={`font-medium ${
                          video.seo_score >= 80 ? 'text-emerald-400' : 
                          video.seo_score >= 60 ? 'text-yellow-400' : 'text-red-400'
                        }`}>{video.seo_score}/100</span>
                      </div>
                      <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                        <div 
                          className={`h-full rounded-full transition-all ${
                            video.seo_score >= 80 ? 'bg-emerald-500' : 
                            video.seo_score >= 60 ? 'bg-yellow-500' : 'bg-red-500'
                          }`}
                          style={{ width: `${video.seo_score}%` }}
                        />
                      </div>
                    </div>
                  )}
                  
                  {/* Actions */}
                  <div className="flex items-center gap-2">
                    {video.status === 'ready' && (
                      <>
                        <Button 
                          size="sm" 
                          onClick={() => {
                            // Navigate to dashboard with this video to edit/publish
                            navigate('/dashboard', { state: { editVideo: video } });
                          }}
                          className="flex-1 bg-indigo-600 hover:bg-indigo-500"
                        >
                          <Edit3 className="w-3 h-3 mr-1" /> Edit
                        </Button>
                        <Button 
                          size="sm" 
                          variant="outline"
                          className="border-zinc-700 hover:bg-zinc-800"
                          onClick={() => {
                            if (video.voiceover_url) {
                              window.open(video.voiceover_url, '_blank');
                            } else {
                              toast.info('Voiceover not available');
                            }
                          }}
                        >
                          <Download className="w-3 h-3" />
                        </Button>
                      </>
                    )}
                    
                    {video.status === 'published' && (
                      <Button 
                        size="sm" 
                        className="flex-1 bg-red-600 hover:bg-red-500"
                        onClick={() => window.open(`https://youtube.com/watch?v=${video.youtube_video_id}`, '_blank')}
                      >
                        <Youtube className="w-3 h-3 mr-1" /> View on YouTube
                      </Button>
                    )}
                    
                    {video.status === 'scheduled' && (
                      <div className="flex-1 text-center text-sm text-indigo-400">
                        <Calendar className="w-4 h-4 inline mr-1" />
                        {formatDate(video.scheduled_at)}
                      </div>
                    )}
                    
                    {video.status === 'failed' && (
                      <Button 
                        size="sm" 
                        className="flex-1 bg-zinc-700 hover:bg-zinc-600"
                        onClick={() => {
                          api.post(`/videos/${video.video_id}/regenerate`, { regenerate_script: true })
                            .then(() => {
                              toast.success('Retrying video generation');
                              fetchVideos();
                            })
                            .catch(() => toast.error('Failed to retry'));
                        }}
                        data-testid={`retry-video-btn-${video.video_id}`}
                      >
                        Retry
                      </Button>
                    )}
                    
                    <Button 
                      size="sm" 
                      variant="ghost"
                      className="text-zinc-500 hover:text-red-400 hover:bg-red-500/10"
                      onClick={() => setShowDeleteConfirm(video.video_id)}
                    >
                      <Trash2 className="w-3 h-3" />
                    </Button>
                  </div>
                </div>
                
                {/* Delete Confirmation */}
                {showDeleteConfirm === video.video_id && (
                  <div className="p-4 bg-red-950/50 border-t border-red-900/50">
                    <p className="text-sm text-red-200 mb-3">Delete this video?</p>
                    <div className="flex gap-2">
                      <Button 
                        size="sm" 
                        variant="outline"
                        className="flex-1 border-zinc-700"
                        onClick={() => setShowDeleteConfirm(null)}
                      >
                        Cancel
                      </Button>
                      <Button 
                        size="sm" 
                        className="flex-1 bg-red-600 hover:bg-red-500"
                        onClick={() => handleDeleteVideo(video.video_id)}
                      >
                        Delete
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </main>

      {/* Video Player Modal */}
      {playingVideo && (
        <div
          className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={() => setPlayingVideo(null)}
          data-testid="video-player-modal"
        >
          <div
            className="bg-zinc-900 rounded-2xl border border-zinc-700 max-w-4xl w-full overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-4 border-b border-zinc-800">
              <h3 className="font-bold truncate pr-4">{playingVideo.title || playingVideo.prompt?.substring(0, 60)}</h3>
              <div className="flex items-center gap-2 shrink-0">
                <Button
                  size="sm"
                  variant="outline"
                  className="border-zinc-700"
                  onClick={() => handleDownload(playingVideo)}
                  data-testid="modal-download-btn"
                >
                  <Download className="w-4 h-4 mr-1" /> Download MP4
                </Button>
                <button
                  onClick={() => setPlayingVideo(null)}
                  className="p-2 hover:bg-zinc-800 rounded-lg"
                  data-testid="close-player-btn"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>
            <video
              controls
              autoPlay
              className="w-full aspect-video bg-black"
              src={`${BACKEND_URL}${playingVideo.video_url}`}
              poster={playingVideo.selected_thumbnail_url?.startsWith('data:') ? undefined : playingVideo.selected_thumbnail_url}
              data-testid="video-player"
            />
            <div className="p-4 flex items-center justify-between text-xs text-zinc-500">
              <span>{playingVideo.rendered_duration ? `${Math.floor(playingVideo.rendered_duration / 60)}:${String(Math.round(playingVideo.rendered_duration % 60)).padStart(2, '0')} min` : ''}</span>
              <span>{playingVideo.file_size_mb ? `${playingVideo.file_size_mb} MB · 1080p HD` : ''}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Library;
