-- ============================================================
--  Trigger: Notify on Orders Change
--  Fires on INSERT, UPDATE, and DELETE on the orders table.
--  Sends a JSON payload to the 'order_updates' channel.
-- ============================================================


-- Trigger function — builds a JSON payload and calls NOTIFY
CREATE OR REPLACE FUNCTION notify_order_change()
RETURNS TRIGGER AS $$

DECLARE
    payload   JSONB;
    row_data  JSONB;

BEGIN

    -- Build the row snapshot based on operation type
    IF (TG_OP = 'DELETE') THEN
        row_data := to_jsonb(OLD);
    ELSE
        row_data := to_jsonb(NEW);
    END IF;


    -- Assemble the notification payload
    payload := jsonb_build_object(
        'operation',  TG_OP,
        'table',      TG_TABLE_NAME,
        'data',       row_data,
        'timestamp',  extract(epoch from now())
    );


    -- Log the event for replay support
    INSERT INTO order_events (operation, order_id, payload)
    VALUES (
        TG_OP,
        (row_data->>'id')::INTEGER,
        payload
    );


    -- Fire the notification on the channel
    PERFORM pg_notify('order_updates', payload::TEXT);


    RETURN NEW;

END;
$$ LANGUAGE plpgsql;


-- Attach the trigger to the orders table
DROP TRIGGER IF EXISTS order_change_trigger ON orders;

CREATE TRIGGER order_change_trigger
    AFTER INSERT OR UPDATE OR DELETE
    ON orders
    FOR EACH ROW
    EXECUTE FUNCTION notify_order_change();
