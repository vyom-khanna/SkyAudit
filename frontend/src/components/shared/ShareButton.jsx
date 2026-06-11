import { Share2, Check } from 'lucide-react';
import { useState } from 'react';

export function ShareButton({ url, title, className = '' }) {
  const [copied, setCopied] = useState(false);

  const handleShare = async () => {
    const shareUrl = url || window.location.href;
    if (navigator.share) {
      try {
        await navigator.share({ title: title || 'SchoolTruth Report', url: shareUrl });
        return;
      } catch (_) {}
    }
    await navigator.clipboard.writeText(shareUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleShare}
      className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm border border-gray-300 hover:bg-gray-50 transition-colors ${className}`}
    >
      {copied ? <Check size={15} className="text-green-600" /> : <Share2 size={15} />}
      {copied ? 'Copied!' : 'Share'}
    </button>
  );
}
