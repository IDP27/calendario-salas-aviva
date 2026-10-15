-- Preserve existing physical holds from option bookings as confirmed reservations.
ALTER TABLE bookings DROP CONSTRAINT bookings_status_check;
UPDATE bookings SET status = CASE
    WHEN status = 'option' THEN 'confirmed'
    WHEN status IN ('pending', 'waiting') THEN 'reserved'
    ELSE status
END;
ALTER TABLE bookings ADD CONSTRAINT bookings_status_check
    CHECK (status IN ('reserved', 'confirmed', 'cancelled'));

-- Idempotent responses should not reintroduce retired status names.
UPDATE idempotency SET response = jsonb_set(
    response, '{status}',
    to_jsonb(CASE response->>'status'
        WHEN 'option' THEN 'confirmed'
        WHEN 'pending' THEN 'reserved'
        WHEN 'waiting' THEN 'reserved'
        ELSE response->>'status'
    END)
) WHERE response->>'status' IN ('option', 'pending', 'waiting');
