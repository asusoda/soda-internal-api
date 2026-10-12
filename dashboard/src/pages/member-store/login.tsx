import { Link, useParams } from 'react-router';
import { AuthFrame } from '../../components/auth-frame';
import { storeLoginUrl, storePath } from './shared';

// Member sign-in for the store: a Discord sign-in through the API, which returns to the store.
export function MemberLoginPage() {
  const prefix = useParams().prefix ?? '';
  return (
    <AuthFrame>
      <div className="rounded-2xl border border-line bg-panel p-6 shadow-xs sm:p-8">
        <h1 className="text-xl font-semibold tracking-tight">Member sign-in</h1>
        <p className="mt-1.5 text-sm text-pretty text-muted">
          Sign in with the Discord account that is in the org's server to order from the store with your points.
        </p>
        <div className="mt-6 flex items-center gap-4">
          <a
            href={storeLoginUrl(prefix)}
            className="flex h-9 items-center rounded-lg bg-fg px-3 text-sm font-medium text-bg hover:opacity-90"
          >
            Sign in with Discord
          </a>
          <Link to={storePath(prefix)} className="text-sm text-muted hover:text-fg">
            Back to the store
          </Link>
        </div>
      </div>
    </AuthFrame>
  );
}
