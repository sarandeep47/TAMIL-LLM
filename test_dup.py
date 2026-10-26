from fact_extractor import extract_facts
from memory_db import initialize_database, get_memory
from pathlib import Path

# Clean DB
db = Path('data/processed/memory_dup_test.db')
if db.exists():
    db.unlink()

import memory_db
memory_db.DB_PATH = db
initialize_database()

msg = 'naa college la cse padichen'
print(f'Input: {msg!r}\n')

facts = extract_facts(msg)
print(f'extract_facts() returned {len(facts)} fact(s):')
for f in facts:
    print(f'  {f.key} = {f.value!r}')

print(f'\nDatabase contents:')
print(f'  user_field_of_study = {get_memory("user_field_of_study")!r}')
print(f'  user_school = {get_memory("user_school")!r}')
