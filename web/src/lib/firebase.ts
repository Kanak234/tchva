import {
  initializeApp,
  getApps,
  type FirebaseApp,
} from 'firebase/app';
import {
  initializeAuth,
  browserLocalPersistence,
  browserSessionPersistence,
  browserPopupRedirectResolver,
  indexedDBLocalPersistence,
  type Auth,
} from 'firebase/auth';

/**
 * Firebase configuration — Section 9.
 *
 * The web config is public by design. It identifies the project;
 * it does not authorise anything. What protects data is firestore.rules
 * plus the ID-token check in api/auth.py.
 *
 * Auth is initialized explicitly with durable browser persistence instead
 * of relying on getAuth() defaults. This is important for the static
 * Firebase Hosting build: a successful popup sign-in must survive the
 * navigation/reload boundary and must not fall back to a signed-out login
 * screen.
 */
const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY || '',
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN || '',
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || '',
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET || '',
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID || '',
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID || '',
};

export function isFirebaseConfigured(): boolean {
  return Boolean(firebaseConfig.apiKey && firebaseConfig.projectId);
}

let _app: FirebaseApp | null = null;
let _auth: Auth | null = null;

export function getFirebaseApp(): FirebaseApp | null {
  if (typeof window === 'undefined') return null;
  if (!isFirebaseConfigured()) return null;
  if (!_app) {
    _app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0];
  }
  return _app;
}

export function getFirebaseAuth(): Auth | null {
  if (_auth) return _auth;
  const app = getFirebaseApp();
  if (!app) return null;

  // Explicitly persist auth in IndexedDB/localStorage, with session storage
  // as a fallback. Also initialize the browser popup resolver explicitly.
  // This removes reliance on environment-dependent getAuth() defaults.
  _auth = initializeAuth(app, {
    persistence: [
      indexedDBLocalPersistence,
      browserLocalPersistence,
      browserSessionPersistence,
    ],
    popupRedirectResolver: browserPopupRedirectResolver,
  });
  _auth.languageCode = 'hi';
  return _auth;
}
