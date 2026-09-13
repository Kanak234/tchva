/**
 * auth.ts — Google sign-in, and the token every API call carries.
 */

import {
  GoogleAuthProvider,
  signInWithPopup,
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

/** Sign in with Google using a popup. Returns a friendly error string, or null on success. */
export async function signInWithGoogle(): Promise<string | null> {
  const auth = getFirebaseAuth();
  if (!auth) return 'Sign-in is not configured on this build.';

  try {
    const provider = new GoogleAuthProvider();
    provider.setCustomParameters({ prompt: 'select_account' });
    await signInWithPopup(auth, provider);

    // A real Google session must never inherit a previously selected demo farm.
    localStorage.removeItem('fk_demo');
    localStorage.removeItem('fk_farm_id');

    return null;
  } catch (err: unknown) {
    return friendlyError(err);
  }
}

/**
 * The token for the next API call, or null when signed out.
 * On a fresh page load Firebase restores the user asynchronously, so wait for
 * that first auth-state result instead of treating currentUser === null as
 * proof that the user is signed out.
 */
export async function getToken(): Promise<string | null> {
  const auth = getFirebaseAuth();
  if (!auth) return null;

  let user = auth.currentUser;
  if (!user) {
    user = await new Promise<User | null>((resolve) => {
      let settled = false;
      const unsubscribe = onAuthStateChanged(auth, (nextUser) => {
        if (settled) return;
        settled = true;
        unsubscribe();
        resolve(nextUser);
      });
    });
  }

  if (!user) return null;

  try {
    return await user.getIdToken();
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
    case 'auth/popup-blocked':
      return 'Your browser blocked the Google sign-in popup. Allow popups for fasal-kavach.web.app and try again.';
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
