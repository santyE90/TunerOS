import { Suspense } from "react";

import { InvestigationWorkspace } from "../../../../components/investigation/investigation-workspace";

export default function InvestigationPage() {
  return (
    <Suspense fallback={<div className="investigation-empty">Loading investigation workspace…</div>}>
      <InvestigationWorkspace />
    </Suspense>
  );
}

