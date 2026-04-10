import { useMemo, useState } from 'react';
import { ChevronDown, LoaderCircle, Plus, Trash2, X } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import { Input } from '@/components/ui/input';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';
import type { OfficialFeedSource } from '@/types/crisis';

type SourceMultiSelectProps = {
  sources: OfficialFeedSource[];
  selectedIds: string[];
  isAddingSource: boolean;
  deletingSourceIds: string[];
  onChange: (nextSelectedIds: string[]) => void;
  onAddSource: (input: string) => Promise<boolean>;
  onDeleteSource: (source: OfficialFeedSource) => Promise<boolean>;
};

export function SourceMultiSelect({
  sources,
  selectedIds,
  isAddingSource,
  deletingSourceIds,
  onChange,
  onAddSource,
  onDeleteSource,
}: SourceMultiSelectProps) {
  const [open, setOpen] = useState(false);
  const [isAddFormOpen, setIsAddFormOpen] = useState(false);
  const [pendingInput, setPendingInput] = useState('');
  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  const deletingSet = useMemo(() => new Set(deletingSourceIds), [deletingSourceIds]);

  const triggerLabel = useMemo(() => {
    if (selectedIds.length === 0) return 'Select one or more sources';
    if (selectedIds.length === 1) {
      return sources.find((source) => source.id === selectedIds[0])?.name ?? 'Select one or more sources';
    }
    return `${selectedIds.length} selected`;
  }, [selectedIds, sources]);

  const toggleSource = (sourceId: string) => {
    if (selectedSet.has(sourceId)) {
      onChange(selectedIds.filter((selectedId) => selectedId !== sourceId));
      return;
    }
    onChange([...selectedIds, sourceId]);
  };

  const handleAddSource = async () => {
    const success = await onAddSource(pendingInput);
    if (!success) return;
    setPendingInput('');
    setIsAddFormOpen(false);
  };

  return (
    <div className="space-y-2">
      <label className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Source</label>
      <Popover open={open} onOpenChange={setOpen}>
        <div className="flex items-center gap-2">
          <PopoverTrigger asChild>
            <Button
              type="button"
              variant="outline"
              className="flex-1 justify-between border-border/60 bg-background/40 text-left text-sm font-normal text-foreground hover:bg-accent/40"
            >
              <span className={cn('truncate', selectedIds.length === 0 && 'text-muted-foreground')}>{triggerLabel}</span>
              <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
            </Button>
          </PopoverTrigger>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => {
              setOpen(true);
              setIsAddFormOpen(true);
            }}
            className="border-border/60 bg-background/40 hover:bg-accent/40"
          >
            <Plus className="h-4 w-4" />
            Add Source
          </Button>
        </div>
        <PopoverContent className="w-[360px] border-border/60 bg-background/95 p-0" align="start">
          <div className="border-b border-border/60 p-2">
            <div className="flex items-center justify-between gap-2">
              <div className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Manage Sources</div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setIsAddFormOpen((current) => {
                    const next = !current;
                    if (!next) {
                      setPendingInput('');
                    }
                    return next;
                  });
                }}
                className="h-8 px-2 text-xs"
              >
                {isAddFormOpen ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
                {isAddFormOpen ? 'Close' : 'Add Source'}
              </Button>
            </div>

            {isAddFormOpen ? (
              <div className="mt-2 flex flex-col gap-2 sm:flex-row">
                <Input
                  value={pendingInput}
                  onChange={(event) => setPendingInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault();
                      void handleAddSource();
                    }
                  }}
                  placeholder="@channel, username, or https://t.me/channel"
                  className="border-border/60 bg-background/70"
                />
                <Button type="button" size="sm" onClick={() => void handleAddSource()} disabled={isAddingSource || pendingInput.trim().length === 0}>
                  {isAddingSource ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                  Add
                </Button>
              </div>
            ) : null}
          </div>

          <Command>
            <CommandInput placeholder="Search sources..." />
            <CommandList className="max-h-72">
              <CommandEmpty>No sources found.</CommandEmpty>
              <CommandGroup>
                <CommandItem value="all sources" onSelect={() => onChange([])} className="flex items-center gap-3">
                  <Checkbox checked={selectedIds.length === 0} className="pointer-events-none" />
                  <span className="truncate font-medium">All Sources</span>
                </CommandItem>
                {sources.map((source) => {
                  const isSelected = selectedSet.has(source.id);
                  const isDeleting = deletingSet.has(source.id);

                  return (
                    <CommandItem
                      key={source.id}
                      value={`${source.name} ${source.username}`}
                      onSelect={() => toggleSource(source.id)}
                      className="flex items-center gap-3 pr-1"
                    >
                      <Checkbox checked={isSelected} className="pointer-events-none" />
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm">{source.name}</div>
                        <div className="truncate text-xs text-muted-foreground">@{source.username}</div>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        disabled={isDeleting}
                        onMouseDown={(event) => {
                          event.preventDefault();
                          event.stopPropagation();
                        }}
                        onClick={(event) => {
                          event.preventDefault();
                          event.stopPropagation();
                          void onDeleteSource(source);
                        }}
                        className="h-7 w-7 text-muted-foreground hover:text-destructive"
                        aria-label={`Delete ${source.name}`}
                      >
                        {isDeleting ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                      </Button>
                    </CommandItem>
                  );
                })}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  );
}
