-- Pack name alignment for ptcgp-assets sets.json.packs display names.
-- Run only after reviewing mapping and on a copied database first.
-- 变更原因：sqlite3 默认遇错继续执行，guard 失败时必须立即停止以避免后续 UPDATE 写入。
.bail on

BEGIN IMMEDIATE;

CREATE TEMP TABLE _pack_name_alignment (
    set_code TEXT NOT NULL,
    old_name TEXT NOT NULL,
    new_name TEXT NOT NULL,
    PRIMARY KEY (set_code, old_name)
);

INSERT INTO _pack_name_alignment (set_code, old_name, new_name) VALUES
    ('A1a', 'Mew', 'Mythical Island'),
    ('A2a', 'Arceus', 'Triumphant Light'),
    ('A2b', 'Shining', 'Shining Revelry'),
    ('A3a', 'Extradimensional', 'Extradimensional Crisis'),
    ('A3b', 'Eevee', 'Eevee Grove'),
    ('A4a', 'Secluded', 'Secluded Springs'),
    ('A4b', 'Deluxe', 'Deluxe Pack ex'),
    ('B2', 'Gardevoir', 'Fantastical Parade'),
    ('B2a', 'Paldean', 'Paldean Wonders'),
    ('PROMO-A', 'Vol. 1', 'Promo Pack A Series Vol. 1'),
    ('PROMO-A', 'Vol. 2', 'Promo Pack A Series Vol. 2'),
    ('PROMO-A', 'Vol. 3', 'Promo Pack A Series Vol. 3'),
    ('PROMO-A', 'Vol. 4', 'Promo Pack A Series Vol. 4'),
    ('PROMO-A', 'Vol. 5', 'Promo Pack A Series Vol. 5'),
    ('PROMO-A', 'Vol. 6', 'Promo Pack A Series Vol. 6'),
    ('PROMO-A', 'Vol. 7', 'Promo Pack A Series Vol. 7'),
    ('PROMO-A', 'Vol. 8', 'Promo Pack A Series Vol. 8'),
    ('PROMO-A', 'Vol. 9', 'Promo Pack A Series Vol. 9'),
    ('PROMO-A', 'Vol. 10', 'Promo Pack A Series Vol. 10'),
    ('PROMO-A', 'Vol. 11', 'Promo Pack A Series Vol. 11'),
    ('PROMO-A', 'Vol. 12', 'Promo Pack A Series Vol. 12'),
    ('PROMO-A', 'Vol. 13', 'Promo Pack A Series Vol. 13'),
    ('PROMO-B', 'B Series Vol. 1', 'Promo Pack B Series Vol. 1'),
    ('PROMO-B', 'B Series Vol. 2', 'Promo Pack B Series Vol. 2'),
    ('PROMO-B', 'B Series Vol. 3', 'Promo Pack B Series Vol. 3'),
    ('PROMO-B', 'B Series Vol. 4', 'Promo Pack B Series Vol. 4'),
    ('PROMO-B', 'B Series Vol. 5', 'Promo Pack B Series Vol. 5');

CREATE TEMP TABLE _pack_name_alignment_guard (ok INTEGER NOT NULL);

SELECT 'mapping_rows' AS check_name, COUNT(*) AS row_count FROM _pack_name_alignment;

SELECT 'old_pack_rows' AS check_name, COUNT(*) AS row_count
FROM packs
JOIN _pack_name_alignment AS mapping
    ON packs.set_code = mapping.set_code
    AND packs.name = mapping.old_name;

SELECT 'new_name_conflicts' AS check_name, COUNT(*) AS row_count
FROM packs
JOIN _pack_name_alignment AS mapping
    ON packs.name = mapping.new_name;

SELECT 'card_pack_duplicate_conflicts' AS check_name, COUNT(*) AS row_count
FROM card_packs AS old_link
JOIN _pack_name_alignment AS mapping
    ON old_link.pack_name = mapping.old_name
JOIN card_packs AS new_link
    ON new_link.card_id = old_link.card_id
    AND new_link.pack_name = mapping.new_name;

INSERT INTO _pack_name_alignment_guard (ok)
SELECT CASE
    WHEN EXISTS (
        SELECT 1
        FROM _pack_name_alignment AS mapping
        WHERE NOT EXISTS (
            SELECT 1
            FROM packs
            WHERE packs.set_code = mapping.set_code
                AND packs.name = mapping.old_name
        )
    ) THEN NULL
    ELSE 1
END;

INSERT INTO _pack_name_alignment_guard (ok)
SELECT CASE
    WHEN EXISTS (
        SELECT 1
        FROM packs
        JOIN _pack_name_alignment AS mapping
            ON packs.name = mapping.new_name
    ) THEN NULL
    ELSE 1
END;

INSERT INTO _pack_name_alignment_guard (ok)
SELECT CASE
    WHEN EXISTS (
        SELECT 1
        FROM card_packs AS old_link
        JOIN _pack_name_alignment AS mapping
            ON old_link.pack_name = mapping.old_name
        JOIN card_packs AS new_link
            ON new_link.card_id = old_link.card_id
            AND new_link.pack_name = mapping.new_name
    ) THEN NULL
    ELSE 1
END;

UPDATE packs
SET
    name = (
        SELECT mapping.new_name
        FROM _pack_name_alignment AS mapping
        WHERE mapping.set_code = packs.set_code
            AND mapping.old_name = packs.name
    ),
    label_data = CASE
        WHEN json_valid(label_data) THEN json_set(
            label_data,
            '$.en',
            (
                SELECT mapping.new_name
                FROM _pack_name_alignment AS mapping
                WHERE mapping.set_code = packs.set_code
                    AND mapping.old_name = packs.name
            )
        )
        ELSE json_object(
            'en',
            (
                SELECT mapping.new_name
                FROM _pack_name_alignment AS mapping
                WHERE mapping.set_code = packs.set_code
                    AND mapping.old_name = packs.name
            )
        )
    END,
    updated_at = CURRENT_TIMESTAMP
WHERE EXISTS (
    SELECT 1
    FROM _pack_name_alignment AS mapping
    WHERE mapping.set_code = packs.set_code
        AND mapping.old_name = packs.name
);

UPDATE card_packs
SET
    pack_name = (
        SELECT mapping.new_name
        FROM _pack_name_alignment AS mapping
        WHERE mapping.old_name = card_packs.pack_name
    ),
    updated_at = CURRENT_TIMESTAMP
WHERE EXISTS (
    SELECT 1
    FROM _pack_name_alignment AS mapping
    WHERE mapping.old_name = card_packs.pack_name
);

UPDATE account_pack_config
SET
    booster_name = (
        SELECT mapping.new_name
        FROM _pack_name_alignment AS mapping
        WHERE mapping.old_name = account_pack_config.booster_name
    ),
    updated_at = CURRENT_TIMESTAMP
WHERE EXISTS (
    SELECT 1
    FROM _pack_name_alignment AS mapping
    WHERE mapping.old_name = account_pack_config.booster_name
);

UPDATE pack_records
SET pack_name = (
    SELECT mapping.new_name
    FROM _pack_name_alignment AS mapping
    WHERE mapping.old_name = pack_records.pack_name
)
WHERE EXISTS (
    SELECT 1
    FROM _pack_name_alignment AS mapping
    WHERE mapping.old_name = pack_records.pack_name
);

SELECT 'post_pack_label_alignment_failures' AS check_name, COUNT(*) AS row_count
FROM packs
JOIN _pack_name_alignment AS mapping
    ON packs.name = mapping.new_name
WHERE packs.name != json_extract(packs.label_data, '$.en');

SELECT 'post_card_pack_duplicate_groups' AS check_name, COUNT(*) AS row_count
FROM (
    SELECT card_id, pack_name
    FROM card_packs
    GROUP BY card_id, pack_name
    HAVING COUNT(*) > 1
);

INSERT INTO _pack_name_alignment_guard (ok)
SELECT CASE
    WHEN EXISTS (
        SELECT 1
        FROM packs
        JOIN _pack_name_alignment AS mapping
            ON packs.name = mapping.new_name
        WHERE packs.name != json_extract(packs.label_data, '$.en')
    ) THEN NULL
    ELSE 1
END;

INSERT INTO _pack_name_alignment_guard (ok)
SELECT CASE
    WHEN EXISTS (
        SELECT 1
        FROM card_packs
        GROUP BY card_id, pack_name
        HAVING COUNT(*) > 1
    ) THEN NULL
    ELSE 1
END;

DROP TABLE _pack_name_alignment_guard;
DROP TABLE _pack_name_alignment;

COMMIT;
