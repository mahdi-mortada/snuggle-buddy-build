import { Filter, RotateCcw } from 'lucide-react';

import { FilterMultiSelect } from '@/components/official-feeds/FilterMultiSelect';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { FilterOption } from '@/lib/officialFeedFilters';

type OfficialFeedFilterPanelProps = {
  sourceOptions: FilterOption[];
  regionOptions: FilterOption[];
  selectedSources: string[];
  selectedRegionIds: string[];
  keyword: string;
  totalResults: number;
  filteredResults: number;
  regionOptionsReady: boolean;
  onSourceChange: (nextSelectedSources: string[]) => void;
  onRegionChange: (nextSelectedRegionIds: string[]) => void;
  onKeywordChange: (nextKeyword: string) => void;
  onClearFilters: () => void;
};

export function OfficialFeedFilterPanel({
  sourceOptions,
  regionOptions,
  selectedSources,
  selectedRegionIds,
  keyword,
  totalResults,
  filteredResults,
  regionOptionsReady,
  onSourceChange,
  onRegionChange,
  onKeywordChange,
  onClearFilters,
}: OfficialFeedFilterPanelProps) {
  const hasActiveFilters = selectedSources.length > 0 || selectedRegionIds.length > 0 || keyword.trim().length > 0;

  return (
    <section className="glass-panel border border-border/50 p-4 md:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-2">
          <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-[11px] uppercase tracking-[0.24em] text-primary">
            <Filter className="h-3.5 w-3.5" />
            Advanced Filters
          </div>
          <div>
            <h2 className="text-lg font-semibold text-foreground">Filter Official Feed Posts</h2>
            <p className="max-w-3xl text-sm text-muted-foreground">
              Combine source, Lebanon location, and keyword filters with AND logic. Region matching accepts English and Arabic names based on the project GeoJSON location data.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="border border-border/60 bg-secondary/50 text-xs">
            {filteredResults} of {totalResults} posts
          </Badge>
          <Button
            type="button"
            variant="outline"
            onClick={onClearFilters}
            disabled={!hasActiveFilters}
            className="border-border/60 bg-background/40 hover:bg-accent/40"
          >
            <RotateCcw className="mr-2 h-4 w-4" />
            Clear Filters
          </Button>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <FilterMultiSelect
          label="News Sources"
          options={sourceOptions}
          selectedIds={selectedSources}
          placeholder="Select one or more sources"
          searchPlaceholder="Search sources..."
          onChange={onSourceChange}
        />

        <FilterMultiSelect
          label="Regions"
          options={regionOptions}
          selectedIds={selectedRegionIds}
          placeholder={regionOptionsReady ? 'Select Beirut, Hamra, بيروت...' : 'Loading GeoJSON regions...'}
          searchPlaceholder="Search English or Arabic names..."
          disabled={!regionOptionsReady}
          onChange={onRegionChange}
        />

        <div className="space-y-2">
          <label htmlFor="official-feed-keyword-filter" className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
            Keywords
          </label>
          <Input
            id="official-feed-keyword-filter"
            value={keyword}
            onChange={(event) => onKeywordChange(event.target.value)}
            placeholder="Search protest, airport, احتجاج..."
            className="border-border/60 bg-background/40"
          />
          <p className="text-[11px] text-muted-foreground">
            Partial, case-insensitive matching is applied across feed content, publisher names, and detected tags.
          </p>
        </div>
      </div>
    </section>
  );
}
