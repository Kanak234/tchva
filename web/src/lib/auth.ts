/**
 * auth.ts — Google sign-in, and the token every API call carries.
 */

import {
  GoogleAuthProvider,
  getRedirectResult,
  signInWithRedirect,
  signOut,
  onAuthStateChanged,
  type User,
} from 'firebase/auth';
import { getFirebaseAuth, isFirebaseConfigured } from './firebase';

export const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE !== 'false';

/** Firebase is unusable without a configured project. */
export function canSignIn(): boolean {
  return isFirebaseConfigured();
}

/** Step 1: Sign in with Google. Returns a friendly error string, or null on success. */
export async function signInWithGoogle(): Promise<string | null> {
  const auth = getFirebaseAuth();
  if (!auth) return 'Sign-in is not configured on this build.';

  try {
    const provider = new GoogleAuthProvider();
    provider.setCustomParameters({ prompt: 'select_account' });
    await signInWithRedirect(auth, provider);
    return null;
  } catch (err: unknown) {
    return friendlyError(err);
  }
}

/**
 * Complete the redirect flow after Firebase returns to the app.
 * Redirect sign-in can restore currentUser asynchronously, so the caller
 * should still keep watchAuth() active as the final session signal.
 */
export async function finishGoogleRedirect(): Promise<string | null> {
  const auth = getFirebaseAuth();
  if (!auth) return 'Sign-in is not configured on this build.';

  try {
    await getRedirectResult(auth);
    return null;
  } catch (err: unknown) {
    return friendlyError(err);
  }
}

/**
 * The token for the next API call, or null when signed out.
 * api.ts calls this before every request.
 */
export async function getToken(): Promise<string | null> {
  const auth = getFirebaseAuth();
  if (!auth?.currentUser) return null;
  try {
    return await auth.currentUser.getIdToken();
  } catch {
    return null;
  }
}

export function currentUser(): User | null {
  return getFirebaseAuth()?.currentUser ?? null;
}

export function isSignedIn(): boolean {
  return Boolean(currentUser());
}

/** Firebase restores the session asynchronously on page load; wait for it. */
export function watchAuth(cb: (user: User | null) => void): () => void {
  const auth = getFirebaseAuth();
  if (!auth) {
    cb(null);
    return () => {};
  }
  return onAuthStateChanged(auth, cb);
}

export async function signOutUser(): Promise<void> {
  const auth = getFirebaseAuth();
  if (auth) await signOut(auth);
  localStorage.removeItem('fk_farm_id');
  localStorage.removeItem('fk_demo');
}

/**
 * Firebase error codes translation.
 */
function friendlyError(err: unknown): string {
  const code = (err as { code?: string })?.code || '';
  switch (code) {
    case 'auth/popup-closed-by-user':
      return 'The sign-in popup was closed before completion.';
    case 'auth/cancelled-popup-request':
      return 'Sign-in request was cancelled. Try again.';
    case 'auth/network-request-failed':
      return 'No internet connection. Check your network.';
    case 'auth/unauthorized-domain':
      return 'This website is not authorized for Google sign-in. Add fasal-kavach.web.app to Firebase Authentication authorized domains.';
    case 'auth/operation-not-allowed':
      return 'Google sign-in is disabled in Firebase Authentication.';
    case 'auth/api-key-not-valid':
      return 'The Firebase web API key is invalid for this build. Rebuild the site with the current Firebase web configuration.';
    default:
      return (err as Error)?.message || 'Something went wrong. Try again.';
  }
}
