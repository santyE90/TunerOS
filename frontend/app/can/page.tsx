import { CanExplorerProvider } from "../../components/can/can-explorer-provider";
import { CanExplorerWorkspace } from "../../components/can/can-explorer-workspace";

export default function CanExplorerPage() {
  return (
    <CanExplorerProvider>
      <CanExplorerWorkspace />
    </CanExplorerProvider>
  );
}
