import { useMemo, useState } from 'react';
import { Check, ChevronDown } from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';

type FilterOption = {
  id: string;
  label: string;
  searchText?: string;
};

type FilterMultiSelectProps = {
  label: string;
  options: FilterOption[];
  selectedIds: string[];
  placeholder: string;
  searchPlaceholder: string;
  allOptionLabel: string;
  disabled?: boolean;
  onChange: (nextSelectedIds: string[]) => void;
};

export function FilterMultiSelect({
  label,
  options,
  selectedIds,
  placeholder,
  searchPlaceholder,
  allOptionLabel,
  disabled = false,
  onChange,
}: FilterMultiSelectProps) {
  const [open, setOpen] = useState(false);
  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  const triggerLabel = useMemo(() => {
    if (selectedIds.length === 0) return placeholder;
    if (selectedIds.length === 1) {
      return options.find((option) => option.id === selectedIds[0])?.label ?? placeholder;
    }
    return `${selectedIds.length} selected`;
  }, [options, placeholder, selectedIds]);

  const toggleOption = (optionId: string) => {
    if (selectedSet.has(optionId)) {
      onChange(selectedIds.filter((selectedId) => selectedId !== optionId));
      return;
    }
    onChange([...selectedIds, optionId]);
  };

  return (
    <div className="space-y-2">
      <label className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">{label}</label>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            disabled={disabled}
            className="w-full justify-between border-border/60 bg-background/40 text-left text-sm font-normal text-foreground hover:bg-accent/40"
          >
            <span className={cn('truncate', selectedIds.length === 0 && 'text-muted-foreground')}>{triggerLabel}</span>
            <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[320px] border-border/60 bg-background/95 p-0" align="start">
          <Command>
            <CommandInput placeholder={searchPlaceholder} />
            <CommandList>
              <CommandEmpty>No matches found.</CommandEmpty>
              <CommandGroup>
                <CommandItem
                  value={allOptionLabel}
                  onSelect={() => onChange([])}
                  className="flex items-center gap-2"
                >
                  <span
                    className={cn(
                      'flex h-4 w-4 items-center justify-center rounded border border-border/60 text-primary',
                      selectedIds.length === 0 ? 'bg-primary/10' : 'bg-transparent',
                    )}
                  >
                    {selectedIds.length === 0 ? <Check className="h-3 w-3" /> : null}
                  </span>
                  <span className="truncate font-medium">{allOptionLabel}</span>
                </CommandItem>
                {options.map((option) => {
                  const selected = selectedSet.has(option.id);
                  return (
                    <CommandItem
                      key={option.id}
                      value={`${option.label} ${option.searchText ?? ''}`}
                      onSelect={() => toggleOption(option.id)}
                      className="flex items-center gap-2"
                    >
                      <span
                        className={cn(
                          'flex h-4 w-4 items-center justify-center rounded border border-border/60 text-primary',
                          selected ? 'bg-primary/10' : 'bg-transparent',
                        )}
                      >
                        {selected ? <Check className="h-3 w-3" /> : null}
                      </span>
                      <span className="truncate">{option.label}</span>
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
