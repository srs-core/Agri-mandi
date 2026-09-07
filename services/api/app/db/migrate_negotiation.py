import logging
from sqlalchemy import text
from app.db.session import engine

logger = logging.getLogger(__name__)

def migrate_negotiation_schema() -> None:
    """Apply DDL adjustments for negotiation and produce lot zero quantity support."""
    if engine.dialect.name != "postgresql":
        logger.info("Skipping PostgreSQL DDL migrations for dialect: %s", engine.dialect.name)
        return
    with engine.begin() as conn:
        # 1. Update produce_lots constraint
        conn.execute(text("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'ck_produce_lots_available_quantity_positive'
                ) THEN
                    ALTER TABLE produce_lots DROP CONSTRAINT ck_produce_lots_available_quantity_positive;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'ck_produce_lots_available_quantity_nonnegative'
                ) THEN
                    ALTER TABLE produce_lots ADD CONSTRAINT ck_produce_lots_available_quantity_nonnegative CHECK (available_quantity >= 0);
                END IF;

                -- Update offers status check constraint to include 'countered'
                IF EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'ck_offers_offer_status'
                ) THEN
                    ALTER TABLE offers DROP CONSTRAINT ck_offers_offer_status;
                END IF;

                ALTER TABLE offers ADD CONSTRAINT ck_offers_offer_status
                    CHECK (status IN ('pending', 'countered', 'accepted', 'declined', 'expired', 'withdrawn'));
            END $$;
        """))

        # 2. Add columns to offers table
        conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'offers' AND column_name = 'current_price_per_unit'
                ) THEN
                    ALTER TABLE offers ADD COLUMN current_price_per_unit NUMERIC(14, 2);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'offers' AND column_name = 'current_quantity'
                ) THEN
                    ALTER TABLE offers ADD COLUMN current_quantity NUMERIC(14, 3);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'offers' AND column_name = 'current_proposer_user_id'
                ) THEN
                    ALTER TABLE offers ADD COLUMN current_proposer_user_id UUID REFERENCES users(id) ON DELETE SET NULL;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'offers' AND column_name = 'current_proposer_role'
                ) THEN
                    ALTER TABLE offers ADD COLUMN current_proposer_role VARCHAR(32);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'offers' AND column_name = 'response_required_from_user_id'
                ) THEN
                    ALTER TABLE offers ADD COLUMN response_required_from_user_id UUID REFERENCES users(id) ON DELETE SET NULL;
                END IF;
            END $$;
        """))

        # 3. Create offer_proposals table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS offer_proposals (
                id UUID PRIMARY KEY,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                offer_id UUID NOT NULL REFERENCES offers(id) ON DELETE CASCADE,
                proposer_user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
                proposer_role VARCHAR(32) NOT NULL,
                price_per_unit NUMERIC(14, 2) NOT NULL,
                quantity NUMERIC(14, 3) NOT NULL,
                notes TEXT,
                status_at_step VARCHAR(32) NOT NULL DEFAULT 'proposed',
                CONSTRAINT proposal_quantity_positive CHECK (quantity > 0),
                CONSTRAINT proposal_price_nonnegative CHECK (price_per_unit >= 0)
            );
            CREATE INDEX IF NOT EXISTS ix_offer_proposals_offer_created ON offer_proposals (offer_id, created_at);
        """))

        # 4. Backfill existing offers
        conn.execute(text("""
            UPDATE offers o
            SET
                current_price_per_unit = COALESCE(o.current_price_per_unit, o.offered_price_per_unit),
                current_quantity = COALESCE(o.current_quantity, o.offered_quantity),
                current_proposer_user_id = COALESCE(o.current_proposer_user_id, o.buyer_user_id),
                current_proposer_role = COALESCE(o.current_proposer_role, 'buyer'),
                response_required_from_user_id = COALESCE(o.response_required_from_user_id, p.seller_user_id)
            FROM produce_lots p
            WHERE o.produce_lot_id = p.id
              AND (o.current_price_per_unit IS NULL OR o.current_proposer_user_id IS NULL);
        """))

    logger.info("Negotiation schema migration executed successfully.")

if __name__ == "__main__":
    migrate_negotiation_schema()
    print("Migration complete.")
