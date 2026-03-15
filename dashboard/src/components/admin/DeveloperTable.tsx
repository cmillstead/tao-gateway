import { useState, useMemo } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { SUBNET_DISPLAY_NAMES } from "@/components/usage/subnet-constants";
import { formatRelativeTime } from "@/lib/format";
import type { DeveloperSummary } from "@/types/admin";

interface DeveloperTableProps {
  developers: DeveloperSummary[];
}

type SortField = "email" | "signup_date" | "last_active" | "total_requests";
type SortDirection = "asc" | "desc";

function formatDate(isoTime: string): string {
  return new Date(isoTime).toLocaleDateString();
}

function SortableHeader({
  field,
  label,
  currentField,
  direction,
  onSort,
  className,
}: {
  field: SortField;
  label: string;
  currentField: SortField;
  direction: SortDirection;
  onSort: (field: SortField) => void;
  className?: string;
}) {
  const indicator = currentField === field ? (direction === "asc" ? " ↑" : " ↓") : "";
  const ariaSortValue = currentField === field ? (direction === "asc" ? "ascending" as const : "descending" as const) : undefined;

  return (
    <TableHead
      className={`cursor-pointer select-none ${className ?? ""}`}
      onClick={() => onSort(field)}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSort(field); } }}
      tabIndex={0}
      role="columnheader"
      aria-sort={ariaSortValue}
    >
      {label}{indicator}
    </TableHead>
  );
}

export function DeveloperTable({ developers }: DeveloperTableProps) {
  const [sortField, setSortField] = useState<SortField>("last_active");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDirection("desc");
    }
  };

  const sorted = useMemo(() => {
    return [...developers].sort((a, b) => {
      const dir = sortDirection === "asc" ? 1 : -1;
      switch (sortField) {
        case "email":
          return dir * a.email.localeCompare(b.email);
        case "signup_date":
          return dir * a.signup_date.localeCompare(b.signup_date);
        case "last_active":
          return dir * ((a.last_active ?? "").localeCompare(b.last_active ?? ""));
        case "total_requests":
          return dir * (a.total_requests - b.total_requests);
        default:
          return 0;
      }
    });
  }, [developers, sortField, sortDirection]);

  const subnetNames = useMemo(() => {
    return [
      ...new Set(developers.flatMap((d) => Object.keys(d.requests_by_subnet))),
    ].sort();
  }, [developers]);

  if (developers.length === 0) {
    return (
      <div className="py-8 text-center">
        <p className="text-sm text-muted-foreground">No developers yet.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <Table>
        <TableHeader>
          <TableRow>
            <SortableHeader field="email" label="Email" currentField={sortField} direction={sortDirection} onSort={handleSort} />
            <SortableHeader field="signup_date" label="Signup" currentField={sortField} direction={sortDirection} onSort={handleSort} />
            <SortableHeader field="last_active" label="Last Active" currentField={sortField} direction={sortDirection} onSort={handleSort} />
            <SortableHeader field="total_requests" label="Total Requests" currentField={sortField} direction={sortDirection} onSort={handleSort} className="text-right" />
            {subnetNames.map((sn) => (
              <TableHead key={sn} className="text-right">
                {SUBNET_DISPLAY_NAMES[sn] ?? sn}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((dev) => (
            <TableRow key={dev.org_id}>
              <TableCell className="font-medium">{dev.email}</TableCell>
              <TableCell>{formatDate(dev.signup_date)}</TableCell>
              <TableCell>{formatRelativeTime(dev.last_active)}</TableCell>
              <TableCell className="text-right">
                {dev.total_requests.toLocaleString()}
              </TableCell>
              {subnetNames.map((sn) => (
                <TableCell key={sn} className="text-right">
                  {(dev.requests_by_subnet[sn] ?? 0).toLocaleString()}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
