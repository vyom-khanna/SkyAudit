import { CheckCircle, Clock, XCircle, AlertCircle } from 'lucide-react';
import { formatDistanceToNow, parseISO } from 'date-fns';

export function ResponseTracker({ anomaly, notices = [] }) {
  const notice = notices?.[0];
  if (!notice) return null;

  const now = new Date();
  const responseDeadline = notice.response_deadline ? new Date(notice.response_deadline) : null;
  const detectedAt = anomaly.detected_at ? new Date(anomaly.detected_at) : null;
  const noticeSentAt = anomaly.notice_sent_at ? new Date(anomaly.notice_sent_at) : null;
  const isOverdue = responseDeadline && now > responseDeadline;
  const responseReceived = notice.response_received;

  const daysOverdue = isOverdue && !responseReceived
    ? Math.floor((now - responseDeadline) / 86_400_000)
    : 0;

  const day30Deadline = responseDeadline;
  const day60Deadline = responseDeadline ? new Date(responseDeadline.getTime() + 30 * 86_400_000) : null;
  const day90Deadline = responseDeadline ? new Date(responseDeadline.getTime() + 60 * 86_400_000) : null;

  const steps = [
    {
      day: 0,
      label: 'Anomaly detected',
      date: detectedAt,
      done: !!detectedAt,
      icon: CheckCircle,
      color: 'text-green-600',
    },
    {
      day: 0,
      label: `Notice sent to ${notice.sent_to || 'DEO'}`,
      date: noticeSentAt,
      done: !!noticeSentAt,
      icon: CheckCircle,
      color: 'text-green-600',
    },
    {
      day: 30,
      label: 'DEO response due',
      date: day30Deadline,
      done: responseReceived,
      overdue: isOverdue && !responseReceived,
      icon: responseReceived ? CheckCircle : isOverdue ? XCircle : Clock,
      color: responseReceived ? 'text-green-600' : isOverdue ? 'text-red-600' : 'text-yellow-600',
      extra: !responseReceived && day30Deadline
        ? isOverdue
          ? `${daysOverdue} days overdue`
          : `${Math.floor((day30Deadline - now) / 86_400_000)} days remaining`
        : null,
    },
    {
      day: 60,
      label: 'RTI auto-filed',
      date: day60Deadline,
      done: day60Deadline && now > day60Deadline && !responseReceived,
      pending: !isOverdue || responseReceived,
      icon: day60Deadline && now > day60Deadline && !responseReceived ? AlertCircle : Clock,
      color: day60Deadline && now > day60Deadline && !responseReceived ? 'text-orange-600' : 'text-gray-400',
    },
    {
      day: 90,
      label: 'Hall of Shame',
      date: day90Deadline,
      done: day90Deadline && now > day90Deadline && !responseReceived,
      pending: true,
      icon: day90Deadline && now > day90Deadline && !responseReceived ? XCircle : Clock,
      color: day90Deadline && now > day90Deadline && !responseReceived ? 'text-red-700' : 'text-gray-400',
    },
  ];

  return (
    <div className="bg-gray-50 rounded-lg p-3 border border-gray-200">
      <h4 className="text-xs font-semibold text-gray-600 mb-3 uppercase tracking-wide">
        Notice Escalation Timeline
      </h4>
      <div className="space-y-2">
        {steps.map((step, i) => {
          const Icon = step.icon;
          return (
            <div key={i} className="flex items-start gap-2.5">
              <Icon size={14} className={`shrink-0 mt-0.5 ${step.color}`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <span className={`text-xs font-medium ${step.done ? 'text-gray-800' : 'text-gray-400'}`}>
                    Day {step.day}: {step.label}
                  </span>
                  {step.date && (
                    <span className="text-xs text-gray-400 shrink-0">
                      {step.done
                        ? formatDistanceToNow(step.date, { addSuffix: true })
                        : step.date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
                    </span>
                  )}
                </div>
                {step.extra && (
                  <p className={`text-xs mt-0.5 font-medium ${step.overdue ? 'text-red-600' : 'text-yellow-600'}`}>
                    {step.extra}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
