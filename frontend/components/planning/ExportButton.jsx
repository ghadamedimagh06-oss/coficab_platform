import { Download } from 'lucide-react';

export default function ExportButton({ exporting, disabled = false, onExport }) {
  return (
    <button
      type="button"
      onClick={onExport}
      disabled={exporting || disabled}
      className="inline-flex items-center gap-2 rounded-full bg-[#7c3aed] px-5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-[#6d28d9] disabled:opacity-60"
    >
      <Download size={16} />
      {exporting ? 'Exporting' : 'Export'}
    </button>
  );
}
