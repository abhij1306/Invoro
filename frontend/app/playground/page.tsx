'use client';

import { PlaygroundView } from './playground-view';
import { usePlaygroundWorkflow } from './use-playground-workflow';

export default function PlaygroundPage() {
  const workflow = usePlaygroundWorkflow();
  return <PlaygroundView workflow={workflow} />;
}
