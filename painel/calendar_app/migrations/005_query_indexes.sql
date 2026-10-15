CREATE INDEX bookings_reserved_queue ON bookings(queue_number) WHERE status='reserved';
CREATE INDEX allocations_configuration_period ON allocations(configuration_id,start_date,end_exclusive);
CREATE INDEX allocations_booking ON allocations(booking_id);
CREATE INDEX audit_entity_history ON audit(entity_type,entity_id,id DESC);
