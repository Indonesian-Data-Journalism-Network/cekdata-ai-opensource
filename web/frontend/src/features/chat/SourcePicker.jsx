import React, { useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Check, ChevronDown, Database } from 'lucide-react';
import './SourcePicker.css';

export default function SourcePicker({ value, options, disabled, onChange }) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({});
  const trigger = useRef(null);
  const menu = useRef(null);
  const id = useId();
  const selected = options.find(option => option.value === value);
  const close = (restore = false) => {
    setOpen(false);
    if (restore) trigger.current?.focus();
  };

  useEffect(() => {
    if (disabled) setOpen(false);
  }, [disabled]);

  useEffect(() => {
    if (!open) return;
    const place = () => {
      const rect = trigger.current.getBoundingClientRect();
      const width = Math.min(360, window.innerWidth - 24);
      setPosition({ width, left: Math.max(12, Math.min(rect.left, window.innerWidth - width - 12)),
        bottom: window.innerHeight - rect.top + 10,
        maxHeight: Math.max(100, rect.top - 22) });
    };
    place();
    const outside = event => {
      if (!menu.current?.contains(event.target) && !trigger.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener('pointerdown', outside);
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, true);
    const frame = requestAnimationFrame(() => {
      const items = menu.current?.querySelectorAll('[role="menuitemradio"]:not(:disabled)');
      ([...items || []].find(item => item.getAttribute('aria-checked') === 'true') || items?.[0])?.focus();
    });
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener('pointerdown', outside);
      window.removeEventListener('resize', place);
      window.removeEventListener('scroll', place, true);
    };
  }, [open]);

  function navigate(event) {
    if (event.key === 'Escape') { event.preventDefault(); close(true); return; }
    if (event.key === 'Tab') { close(true); return; }
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const items = [...menu.current.querySelectorAll('[role="menuitemradio"]:not(:disabled)')];
    if (!items.length) return;
    const current = items.indexOf(document.activeElement);
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1
      : (current + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
    items[next].focus();
  }

  return <>
    <button ref={trigger} type="button" className="source-picker-trigger" disabled={disabled}
      aria-label={`Topik: ${selected?.label || 'Pilih topik'}`} aria-haspopup="menu"
      aria-expanded={open} aria-controls={open ? id : undefined}
      onClick={() => setOpen(!open)}
      onKeyDown={event => { if (['ArrowDown', 'ArrowUp'].includes(event.key)) { event.preventDefault(); setOpen(true); } }}>
      <Database size={15} aria-hidden="true" />
      <span>{selected?.label || 'Pilih topik'}</span>
      {selected?.preview && <span className="source-picker-tag">Uji coba</span>}
      <ChevronDown size={14} aria-hidden="true" style={{ transform: open ? 'rotate(180deg)' : undefined }} />
    </button>
    {open && createPortal(<div ref={menu} id={id} role="menu" aria-label="Pilih topik"
      className="source-picker-menu" style={position} onKeyDown={navigate}
      onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false); }}>
      <div className="source-picker-heading">Pilih topik</div>
      {options.map(option => <button type="button" key={option.value} role="menuitemradio"
        aria-checked={value === option.value} disabled={!option.enabled} tabIndex={-1}
        className="source-picker-option"
        onClick={() => { onChange(option.value); close(true); }}>
        <span className="source-picker-details">
          <span className="source-picker-name">{option.label}
            {option.preview && <span className="source-picker-tag">Uji coba</span>}
            {!option.enabled && <span className="source-picker-unavailable">Belum tersedia</span>}
          </span>
        </span>
        {value === option.value && <Check size={18} className="source-picker-check" aria-hidden="true" />}
      </button>)}
    </div>, document.body)}
  </>;
}
