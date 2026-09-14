import { OperatorGate } from "@/components/OperatorGate";

export default function OperatorSectionLayout({ children }: { children: React.ReactNode }) {
  return <OperatorGate>{children}</OperatorGate>;
}
