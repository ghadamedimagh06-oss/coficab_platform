import { useDraggable } from '@dnd-kit/core';
import { GripVertical, X } from 'lucide-react';

export default function DepotMarker({ marker, left, label, onDelete }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `marker-${marker.id}`,
    data: { markerId: marker.id, marker },
  });
  const dragStyle = transform ? {
    transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
    zIndex: isDragging ? 35 : undefined,
    opacity: isDragging ? 0.85 : undefined,
  } : undefined;

  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      className="absolute top-0 z-20 flex h-full w-5 cursor-grab items-start justify-center border-x border-red-300 bg-[repeating-linear-gradient(135deg,#ef4444_0,#ef4444_3px,#fee2e2_3px,#fee2e2_6px)] pt-2 active:cursor-grabbing"
      style={{ left: `${left}%`, touchAction: 'none', ...dragStyle }}
      title={label}
    >
      <GripVertical size={10} className="rounded-full bg-white/70 text-red-500" />
      <button
        type="button"
        onPointerDown={(event) => event.stopPropagation()}
        onClick={(event) => {
          event.stopPropagation();
          onDelete?.(marker.id);
        }}
        className="absolute -right-2 top-7 rounded-full bg-white p-0.5 text-red-500 shadow-sm hover:bg-red-50"
        title="Delete marker"
      >
        <X size={10} />
      </button>
    </div>
  );
}
