'use client';
import { CrawlRunScreenContent } from './crawl-run-screen-content';
import { useCrawlRunScreenModel } from './use-crawl-run-screen-model';
type CrawlRunScreenProps = { runId: number };

export function CrawlRunScreen({ runId }: Readonly<CrawlRunScreenProps>) {
  const model = useCrawlRunScreenModel(runId);
  return <CrawlRunScreenContent runId={runId} model={model} />;
}
