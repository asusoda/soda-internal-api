import React from 'react';
import InlineEdit from './InlineEdit';

const OrganizationCard = ({ 
  org, 
  onViewDashboard, 
  onConfigure, 
  onCalendarConfig,
  onRemove, 
  onPrefixUpdate, 
  validatePrefix,
  variant = 'default', // 'officer' or 'existing'
  showRemove = false 
}) => {
  const getVariantStyles = () => {
    switch (variant) {
      case 'officer':
        return {
          card: 'bg-gray-800/50 backdrop-blur-sm p-6 rounded-xl border border-blue-600/50 hover:border-blue-500/50 transition-all duration-200',
          title: 'text-lg font-semibold text-blue-300',
          prefix: 'text-sm text-blue-400 font-mono',
          buttonPrimary: 'bg-blue-600/50 hover:bg-blue-700/50 border-blue-500/50',
          buttonSecondary: 'bg-yellow-600/50 hover:bg-yellow-700/50 border-yellow-500/50',
          buttonDanger: 'bg-red-600/50 hover:bg-red-700/50 border-red-500/50'
        };
      case 'existing':
        return {
          card: 'bg-gray-800/50 backdrop-blur-sm p-6 rounded-xl border border-gray-700/50 hover:border-gray-600/50 transition-all duration-200',
          title: 'text-lg font-semibold text-white',
          prefix: 'text-sm text-gray-300 font-mono',
          buttonPrimary: 'bg-blue-600/50 hover:bg-blue-700/50 border-blue-500/50',
          buttonSecondary: 'bg-yellow-600/50 hover:bg-yellow-700/50 border-yellow-500/50',
          buttonDanger: 'bg-red-600/50 hover:bg-red-700/50 border-red-500/50'
        };
      default:
        return {
          card: 'bg-gray-800/50 backdrop-blur-sm p-6 rounded-xl border border-gray-700/50 hover:border-gray-600/50 transition-all duration-200',
          title: 'text-lg font-semibold text-white',
          prefix: 'text-sm text-gray-300 font-mono',
          buttonPrimary: 'bg-blue-600/50 hover:bg-blue-700/50 border-blue-500/50',
          buttonSecondary: 'bg-yellow-600/50 hover:bg-yellow-700/50 border-yellow-500/50',
          buttonDanger: 'bg-red-600/50 hover:bg-red-700/50 border-red-500/50'
        };
    }
  };

  const styles = getVariantStyles();

  return (
    <div className={styles.card}>
      {/* Header with Icon and Title */}
      <div className="flex items-start space-x-4 mb-4">
        {org.icon_url && (
          <div className="flex-shrink-0">
            <img
              src={org.icon_url}
              alt={`${org.name} icon`}
              className="w-12 h-12 rounded-xl border-2 border-gray-600/50"
            />
          </div>
        )}
        
        <div className="flex-1 min-w-0">
          <h3 className={`${styles.title} mb-2 truncate`}>
            {org.name}
          </h3>
          
          {/* Prefix Section */}
          <div className="flex items-center space-x-2 mb-3">
            <span className="text-sm text-gray-400 font-medium">Prefix:</span>
            <InlineEdit
              value={org.prefix}
              onSave={onPrefixUpdate}
              validation={validatePrefix}
              className={styles.prefix}
              placeholder="Enter prefix..."
            />
          </div>
        </div>
      </div>

      {/* Organization Details */}
      <div className="space-y-2 mb-6">
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-400 font-medium">Guild ID:</span>
          <span className="text-xs text-gray-500 font-mono">{String(org.guild_id)}</span>
        </div>
        
        {org.officer_role_id && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-400 font-medium">Officer Role:</span>
            <span className="text-xs text-green-400 font-mono">{org.officer_role_id}</span>
          </div>
        )}
        
        {/* Calendar Sync Status */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-400 font-medium">Calendar Sync:</span>
          <div className="flex items-center space-x-1">
            <div className={`w-2 h-2 rounded-full ${org.calendar_sync_enabled ? 'bg-green-400' : 'bg-gray-500'}`}></div>
            <span className={`text-xs font-mono ${org.calendar_sync_enabled ? 'text-green-400' : 'text-gray-500'}`}>
              {org.calendar_sync_enabled ? 'Enabled' : 'Disabled'}
            </span>
          </div>
        </div>
        
        {org.notion_database_id && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-400 font-medium">Notion DB:</span>
            <span className="text-xs text-blue-400 font-mono truncate max-w-20">
              {org.notion_database_id.substring(0, 8)}...
            </span>
          </div>
        )}
        
        {org.google_calendar_id && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-400 font-medium">Google Calendar:</span>
            <span className="text-xs text-purple-400 font-mono truncate max-w-20">
              {org.google_calendar_id.substring(0, 8)}...
            </span>
          </div>
        )}
        
        {org.description && (
          <div className="pt-2 border-t border-gray-700/50">
            <p className="text-xs text-gray-400 leading-relaxed">
              {org.description}
            </p>
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="space-y-2">
        <button
          onClick={() => onViewDashboard(org)}
          className={`w-full px-4 py-2 ${styles.buttonPrimary} backdrop-blur-sm rounded-lg text-sm font-medium transition-all duration-200 border hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]`}
        >
          <div className="flex items-center justify-center space-x-2">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            <span>View Dashboard</span>
          </div>
        </button>
        
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => onConfigure(org)}
            className={`px-4 py-2 ${styles.buttonSecondary} backdrop-blur-sm rounded-lg text-xs font-medium transition-all duration-200 border hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]`}
          >
            <div className="flex items-center justify-center space-x-1">
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <span>Roles</span>
            </div>
          </button>
          
          <button
            onClick={() => onCalendarConfig(org)}
            className={`px-4 py-2 ${styles.buttonSecondary} backdrop-blur-sm rounded-lg text-xs font-medium transition-all duration-200 border hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]`}
          >
            <div className="flex items-center justify-center space-x-1">
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <span>Calendar</span>
            </div>
          </button>
        </div>
        
        {showRemove && onRemove && (
          <button
            onClick={() => onRemove(org.id)}
            className={`w-full px-4 py-2 ${styles.buttonDanger} backdrop-blur-sm rounded-lg text-sm font-medium transition-all duration-200 border hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]`}
          >
            <div className="flex items-center justify-center space-x-2">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              <span>Remove</span>
            </div>
          </button>
        )}
      </div>
    </div>
  );
};

export default OrganizationCard;
