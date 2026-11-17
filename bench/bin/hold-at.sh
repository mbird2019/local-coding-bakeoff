#!/bin/bash
# hold-at.sh HH:MM (UTC) : at that time, park the unrun lines of the r9 queues ("#hold " prefix) so each
# queue.sh ends after its running job. Resume: sed -i 's/^#hold //' queues/r9-*.txt and start queue.sh again.
cd /opt/bakeoff
s=$(( $(date -u -d "today $1" +%s) - $(date +%s) )); [ $s -gt 0 ] && sleep $s
for f in queues/r9-split.txt queues/r9-p5000.txt; do sed -i -E '/^(#|$)/!s/^/#hold /' "$f"; done
echo "$(date -u +%FT%TZ) held: $(grep -c '^#hold ' queues/r9-split.txt queues/r9-p5000.txt | tr '\n' ' ')"
