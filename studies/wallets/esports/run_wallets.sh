#!/bin/bash
# one line per account: name address
cd /home/user/polymarket-lab
run() {
  n=$1; a=$2
  python3 -I tools/wallet_check.py $a --monthly > studies/wallets/esports/$n.monthly.txt 2>&1
  python3 -m pmlab.wallet $a --days 14 --max-fills 60000 --json studies/wallets/esports/$n.json > studies/wallets/esports/$n.txt 2>&1
  echo "done $n $(date +%T)"
}
export -f run
cat <<LIST | xargs -P 4 -L 1 bash -c 'run $0 $1'
RITALINEWITHSNUS 0x9d910a16612ac0b6c2d54e7061ac8d4d0a9d6816
DamwonChampions2027 0x3471a897e56a8d3621ca79af87dae4325977f17e
calculate10 0xb35f674af4603c9602dfbf39564087e94897cf4c
gojda 0xd2bb94594762beda042e596598800d83f781bd8e
iii252 0xed446954680979932092e970b443e6ae61e34f76
lonmi2511 0x997cb45c25e94b4ee58c234ce1f211496a0d51f3
BLASTSLAM9WINNER 0x77d9009e5e22d8b7187530c862dd058949b906ed
LIST
