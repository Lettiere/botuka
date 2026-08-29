from django.db import migrations


FORWARD_SQL = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'social_post_save_tb'
          AND policyname = 'social_post_save_owner_policy'
    ) THEN
        CREATE POLICY social_post_save_owner_policy
        ON public.social_post_save_tb
        FOR ALL
        TO botuka_app
        USING (
            usuario_id =
            NULLIF(current_setting('app.user_id', true), '')::bigint
        )
        WITH CHECK (
            usuario_id =
            NULLIF(current_setting('app.user_id', true), '')::bigint
        );
    END IF;
END
$$;

ALTER TABLE public.social_post_save_tb
ENABLE ROW LEVEL SECURITY;


DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'social_block_tb'
          AND policyname = 'social_block_select_policy'
    ) THEN
        CREATE POLICY social_block_select_policy
        ON public.social_block_tb
        FOR SELECT
        TO botuka_app
        USING (
            EXISTS (
                SELECT 1
                FROM public.social_profile_tb p
                WHERE p.id = bloqueador_id
                  AND p.usuario_id =
                      NULLIF(current_setting('app.user_id', true), '')::bigint
            )
            OR
            EXISTS (
                SELECT 1
                FROM public.social_profile_tb p
                WHERE p.id = bloqueado_id
                  AND p.usuario_id =
                      NULLIF(current_setting('app.user_id', true), '')::bigint
            )
        );
    END IF;
END
$$;


DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'social_block_tb'
          AND policyname = 'social_block_insert_policy'
    ) THEN
        CREATE POLICY social_block_insert_policy
        ON public.social_block_tb
        FOR INSERT
        TO botuka_app
        WITH CHECK (
            EXISTS (
                SELECT 1
                FROM public.social_profile_tb p
                WHERE p.id = bloqueador_id
                  AND p.usuario_id =
                      NULLIF(current_setting('app.user_id', true), '')::bigint
            )
        );
    END IF;
END
$$;


DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'social_block_tb'
          AND policyname = 'social_block_delete_policy'
    ) THEN
        CREATE POLICY social_block_delete_policy
        ON public.social_block_tb
        FOR DELETE
        TO botuka_app
        USING (
            EXISTS (
                SELECT 1
                FROM public.social_profile_tb p
                WHERE p.id = bloqueador_id
                  AND p.usuario_id =
                      NULLIF(current_setting('app.user_id', true), '')::bigint
            )
        );
    END IF;
END
$$;

ALTER TABLE public.social_block_tb
ENABLE ROW LEVEL SECURITY;
"""


REVERSE_SQL = """
ALTER TABLE public.social_block_tb DISABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS social_block_delete_policy
ON public.social_block_tb;

DROP POLICY IF EXISTS social_block_insert_policy
ON public.social_block_tb;

DROP POLICY IF EXISTS social_block_select_policy
ON public.social_block_tb;


ALTER TABLE public.social_post_save_tb DISABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS social_post_save_owner_policy
ON public.social_post_save_tb;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("social", "0006_pending_conversation_messages"),
    ]

    operations = [
        migrations.RunSQL(
            sql=FORWARD_SQL,
            reverse_sql=REVERSE_SQL,
        ),
    ]
