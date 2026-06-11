export type PatientSort = "recente" | "nome" | "faltas"

export interface SortablePatient {
  name?: string | null
  created_at?: string | null
  no_show_count?: number | null
}

export function parsePatientSort(raw: string | null): PatientSort {
  return raw === "nome" || raw === "faltas" ? raw : "recente"
}

export function sortPatients<T extends SortablePatient>(patients: T[], sort: PatientSort): T[] {
  const sorted = [...patients]
  if (sort === "nome") {
    sorted.sort((a, b) => (a.name ?? "").localeCompare(b.name ?? "", "pt-BR"))
  } else if (sort === "faltas") {
    sorted.sort((a, b) => (b.no_show_count ?? 0) - (a.no_show_count ?? 0))
  } else {
    sorted.sort(
      (a, b) => new Date(b.created_at ?? 0).getTime() - new Date(a.created_at ?? 0).getTime(),
    )
  }
  return sorted
}
