#!/bin/bash
# smoke.sh HARNESS LANE MODEL [NET]: trivial task through one harness; prints PASS/FAIL.
H=$1 LANE=$2 MODEL=$3 NET=${4:-bakeoff}
B=/opt/bakeoff; R=$B/smoke/$H-$MODEL-$(date +%H%M%S); mkdir -p $R/repo $R/home
cp -a $B/home-template/. $R/home/ 2>/dev/null; chmod -R 777 $R
git -C $R/repo init -q -b main; echo "# smoke" > $R/repo/README.md; git -C $R/repo add -A; git -C $R/repo -c user.name=b -c user.email=b@l commit -qm start; chmod -R 777 $R
printf '%s' "Create a file named hello.py that prints exactly: hello bakeoff. Then run it with python3 to check it works." > $R/home/prompt.txt
start=$(date +%s)
sudo docker run --rm --network $NET -v $R/repo:/work -v $R/home:/home/agent -e HOME=/home/agent -e URL=http://bake-$LANE:8080 -e MODEL=$MODEL -e H=$H -e CTX=32768 -v $B/bin/agent.sh:/agent.sh:ro bakeoff-sandbox timeout 15m bash /agent.sh > $R/log 2>&1
out=$(cd $R/repo && python3 hello.py 2>&1)
[ "$out" = "hello bakeoff" ] && r=PASS || r=FAIL
echo "$r $H $MODEL $(( $(date +%s)-start ))s $R"
