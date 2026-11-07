import React, { useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

export default function WorkspaceDialog({ open, onClose, title, children, className = '', busy = false }) {
  const dialog = useRef(null);
  const titleId = useId();
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement;
    const element = dialog.current;
    element.showModal();
    return () => {
      element.close();
      if (previous?.isConnected) previous.focus({ preventScroll: true });
    };
  }, [open]);
  if (!open) return null;
  return createPortal(<dialog ref={dialog} className={`workspace-dialog ${className}`} aria-labelledby={titleId}
    onCancel={event => { event.preventDefault(); if (!busy) onClose(); }}>
    <div className="workspace-dialog-header">
      <h2 id={titleId}>{title}</h2>
      <button type="button" className="workspace-icon" aria-label={`Tutup ${title}`} disabled={busy} onClick={onClose}><X size={20} /></button>
    </div>
    {children}
  </dialog>, document.body);
}
