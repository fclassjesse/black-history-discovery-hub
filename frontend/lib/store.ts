import { create } from "zustand";

interface SelectionState {
  selectedRecordId: string | null;
  selectedInstitutionId: string | null;
  hoveredRecordId: string | null;
  highlightRecordIds: string[];
  focusInstitutionIds: string[];
  selectRecord: (id: string | null, institutionId?: string | null) => void;
  selectInstitution: (id: string | null) => void;
  hoverRecord: (id: string | null) => void;
  setHighlights: (recordIds: string[], institutionIds: string[]) => void;
  reset: () => void;
}

export const useSelection = create<SelectionState>((set) => ({
  selectedRecordId: null,
  selectedInstitutionId: null,
  hoveredRecordId: null,
  highlightRecordIds: [],
  focusInstitutionIds: [],
  selectRecord: (id, institutionId) => set({ selectedRecordId: id, selectedInstitutionId: institutionId ?? null }),
  selectInstitution: (id) => set({ selectedInstitutionId: id, selectedRecordId: null }),
  hoverRecord: (id) => set({ hoveredRecordId: id }),
  setHighlights: (recordIds, institutionIds) => set({ highlightRecordIds: recordIds, focusInstitutionIds: institutionIds }),
  reset: () => set({ selectedRecordId: null, selectedInstitutionId: null, hoveredRecordId: null, highlightRecordIds: [], focusInstitutionIds: [] }),
}));
