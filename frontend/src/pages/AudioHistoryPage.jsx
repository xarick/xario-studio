import { JobHistory, AUDIO_MODES } from "../components/JobHistory";

export default function AudioHistoryPage() {
  return (
    <JobHistory
      modes={AUDIO_MODES}
      titleKey="audio.historyTitle"
      emptyActionRoute="/audio/new"
      emptyActionKey="audio.empty.addAudio"
    />
  );
}
