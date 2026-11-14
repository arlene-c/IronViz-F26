"""Builds the animated page. Usage: python make_animated.py requests_clean.csv results.csv trace.csv template.html out.html [--mock]"""
import sys, json, pandas as pd, numpy as np
REQ,RES,TRACE,TPL,OUT=sys.argv[1:6]; MOCK="--mock" in sys.argv
TEAMS=["org-prod-core","org-marketing-ai","org-engineering-dev","prj-ai-enterprise-prod","prj-ai-r-and-d","prj-ai-sandbox-testing"]
TEST={"org-engineering-dev","prj-ai-sandbox-testing"}
R=pd.read_csv(REQ,low_memory=False); R["timestamp"]=pd.to_datetime(R.timestamp,utc=True,format="ISO8601")
ok=R[(R.status==200)&(R.exclude_reason.isna())].copy(); ok["tokens"]=ok.input_tokens+ok.output_tokens
D={"mock":MOCK}
D["kpi"]={"calls":int(len(R)),"success":round((R.status==200).mean()*100,1),"tokensB":round(ok.tokens.sum()/1e9,2),
 "callsTest":round(R.tenant.isin(TEST).mean()*100),"tokTest":round(ok[ok.tenant.isin(TEST)].tokens.sum()/ok.tokens.sum()*100)}
D["strip"]={t:{"pts":[int(v) for v in ok[ok.tenant==t].input_tokens.sample(150,random_state=2)],"med":int(ok[ok.tenant==t].input_tokens.median())} for t in TEAMS}
R["day"]=R.timestamp.dt.day; d=R[R.status==429].groupby(["day","provider"]).size().unstack(fill_value=0)
D["rl"]={p:[int(v) for v in d[p]] for p in ["OpenAI","Gemini"]}
S=pd.read_csv(RES); T=pd.read_csv(TRACE); s70=S[S.budget_pct==70]
D["scatter"]={p:[[round(a,2),round(b,2)] for a,b in zip(g.downgraded_pct,g.admitted_pct)] for p,g in s70.groupby("policy")}
D["team"]={p:[round(s70[s70.policy==p]["admitted_pct_"+t].median(),1) for t in TEAMS] for p in ["fcfs","quotas","adaptive","routing"]}
D["qdp"]={p:[round(float(x),1) for x in np.quantile(g.admitted_pct,(np.arange(20)+0.5)/20)] for p,g in s70.groupby("policy")}
D["trace"]={p:list(g.budget_left_pct) for p,g in T[T.budget_pct==70].groupby("policy")}
D["teams"]=TEAMS; D["test"]=sorted(TEST)
html=open(TPL).read().replace("/*__DATA__*/null",json.dumps(D))
open(OUT,"w").write(html); print("ok",len(html))
