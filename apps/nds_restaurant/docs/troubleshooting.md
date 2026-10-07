# Troubleshooting

## POS

| Issue | Fix |
|-------|-----|
| Cannot open POS / no opening | Create POS Opening Entry for the user/profile |
| Not assigned to branch | Add user on Branch → NDS Users |
| Customer search empty | Fill Mobile Number; run `build-search-index` |
| No menu items | Set Default Menu on Restaurant; enable menu; match price list |

## KOT / KDS

| Issue | Fix |
|-------|-----|
| No KOTs | Set KOT Naming Series; create Production Units with Item Groups matching items |
| Items missing on KDS | Item Group not mapped to a Production Unit |
| KOT not printing | Configure unit/room/profile printers |

## Recipes

| Issue | Fix |
|-------|-----|
| No availability badge | Enabled recipe with stock ingredients; warehouse set on profile |
| Shows 0 | Stock in wrong warehouse; drafts reserving qty; recipe qty too high |
| No Stock Entry on pay | Check Error Log; recipe enabled; warehouse on invoice |
