import type { TrackerData } from './lib/types';

declare global {
  interface Window {
    TRACKER_DATA?: TrackerData;
  }
}
