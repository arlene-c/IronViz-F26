"""Descriptive charts only. Usage: python charts/make_static.py clean_requests.csv outdir [--mock]"""
import sys, numpy as np, pandas as pd, matplotlib
from pathlib import Path
matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as mdates
from matplotlib import font_manager as fm
from matplotlib.patches import Patch
REQ,OUT=sys.argv[1:3]; MOCK="--mock" in sys.argv
Path(OUT).mkdir(parents=True, exist_ok=True)
chart_font="DejaVu Sans"
for f in fm.findSystemFonts():
    if "Inter" in f:
        fm.fontManager.addfont(f)
        chart_font="Inter"
plt.rcParams.update({"font.family":chart_font,"font.size":11,"axes.edgecolor":"#c3c2b7","axes.linewidth":0.8,
 "axes.spines.top":False,"axes.spines.right":False,"xtick.color":"#52514e","ytick.color":"#52514e",
 "axes.labelcolor":"#52514e","text.color":"#0b0b0b","figure.facecolor":"#fcfcfb","axes.facecolor":"#fcfcfb","svg.fonttype":"none"})
INK,INK2,GRID="#0b0b0b","#52514e","#e7e6e1"
HI,CTX="#eb6834","#8f8e89"
POL=["fcfs","quotas","adaptive","routing"]
PNAME={"fcfs":"First come, first served","quotas":"Fixed team quotas","adaptive":"Adaptive sharing","routing":"Smart routing"}
PCOL={"fcfs":"#2a78d6","quotas":"#e87ba4","adaptive":"#eda100","routing":"#1baf7a"}
PMARK={"fcfs":"o","quotas":"s","adaptive":"^","routing":"D"}
TEAMS=["org-prod-core","org-marketing-ai","org-engineering-dev","prj-ai-enterprise-prod","prj-ai-r-and-d","prj-ai-sandbox-testing"]
TEST={"org-engineering-dev","prj-ai-sandbox-testing"}; PREMIUM={"gpt-4o","o1-preview","gemini-1.5-pro"}
ALT={}
def title(fig,t,sub=None):
    fig.text(0.012,0.965,t,fontsize=15,fontweight="medium",va="top")
    if sub: fig.text(0.012,0.895,sub,fontsize=10.5,color=INK2,va="top")
def mockmark(fig):
    if MOCK: fig.text(0.99,0.895,"MOCK DATA: replace with real results.csv",ha="right",va="top",fontsize=9,color="#a32d2d",style="italic")
def save(fig,name,alt):
    fig.savefig(f"{OUT}/{name}.png",dpi=300); fig.savefig(f"{OUT}/{name}.svg"); plt.close(fig); ALT[name]=alt

R=pd.read_csv(REQ,low_memory=False); R["timestamp"]=pd.to_datetime(R.timestamp,utc=True,format="ISO8601")
ok=R[(R.status==200)&(R.exclude_reason.isna())].copy()
ok["tokens"]=ok.input_tokens+ok.output_tokens
calls_test=R.tenant.isin(TEST).mean()*100; tok_test=ok[ok.tenant.isin(TEST)].tokens.sum()/ok.tokens.sum()*100

# 01 hero numbers (1D, real)
fig=plt.figure(figsize=(12,2.6)); cards=[(f"{len(R):,}","AI calls in October"),(f"{(R.status==200).mean()*100:.1f}%","succeeded"),
 (f"{ok.tokens.sum()/1e9:.2f}B","tokens processed"),(f"{calls_test:.0f}% → {tok_test:.0f}%","testing teams' share of\ncalls → tokens")]
for i,(v,l) in enumerate(cards):
    ax=fig.add_axes([0.005+i*0.25,0.05,0.24,0.9]); ax.axis("off")
    ax.add_patch(plt.Rectangle((0,0),1,1,transform=ax.transAxes,color="#f1f0ec"))
    ax.text(0.07,0.52,v,fontsize=28 if i<3 else 24,fontweight="medium",color=HI if i==3 else INK,transform=ax.transAxes)
    ax.text(0.07,0.12 if "\n" in l else 0.2,l,fontsize=11.5,color=INK2,transform=ax.transAxes,linespacing=1.3)
save(fig,"01_hero_numbers_1D",f"Four headline numbers: {len(R):,} AI calls in October 2026; {(R.status==200).mean()*100:.1f}% succeeded; {ok.tokens.sum()/1e9:.2f} billion tokens; the two testing teams made {calls_test:.0f}% of calls but used {tok_test:.0f}% of tokens.")

# 02 waffle (1D, real)
fig=plt.figure(figsize=(9,4.6)); title(fig,"Testing teams make a third of the calls but use almost half the tokens","Each square is 1% of the total. Orange is the two testing teams.")
for k,(lab,n) in enumerate([("Share of calls",round(calls_test)),("Share of tokens",round(tok_test))]):
    ax=fig.add_axes([0.03+k*0.5,0.06,0.3,0.68]); ax.set_xlim(0,10); ax.set_ylim(0,10.9); ax.axis("off"); ax.set_aspect("equal")
    for i in range(100):
        c,r=i%10,i//10; ax.add_patch(plt.Rectangle((c+0.08,r+0.08),0.84,0.84,color=HI if i<n else "#d3d1c7",lw=0))
    ax.text(0,10.35,lab,fontsize=12,fontweight="medium")
    fig.text(0.35+k*0.5,0.4,f"{n}%",fontsize=30,fontweight="medium",color=HI); fig.text(0.35+k*0.5,0.32,"testing teams",fontsize=11,color=INK2)
save(fig,"02_waffle_calls_vs_tokens_1D",f"Two 10-by-10 waffle grids. Testing teams account for {calls_test:.0f} of 100 squares for calls and {tok_test:.0f} of 100 squares for tokens.")

# 03 prompt-size distribution strip (1D, real)
rng=np.random.default_rng(1); fig,ax=plt.subplots(figsize=(10,4.8)); title(fig,"Testing teams send much bigger prompts, across the whole range","Each dot is one of 400 randomly sampled successful calls per team. Black tick is the median. Log scale.")
ys={t:i for i,t in enumerate(TEAMS)}; meds={}
for t in TEAMS:
    s=ok[ok.tenant==t].input_tokens.sample(400,random_state=1); y=ys[t]+rng.uniform(-0.28,0.28,len(s))
    ax.scatter(s,y,s=7,color=HI if t in TEST else CTX,alpha=0.55,lw=0)
    m=ok[ok.tenant==t].input_tokens.median(); meds[t]=m; ax.plot([m,m],[ys[t]-0.36,ys[t]+0.36],color=INK,lw=2.2)
    ax.text(m*1.06,ys[t]-0.3,f"median {m:,.0f}",ha="left",va="center",fontsize=9.5,color=INK,bbox=dict(boxstyle="square,pad=0.1",fc="#fcfcfb",ec="none",alpha=0.85))
ax.set_xscale("log"); ax.set_yticks(range(6)); ax.set_yticklabels(TEAMS); ax.set_ylim(5.6,-0.7)
for lbl in ax.get_yticklabels():
    if lbl.get_text() in TEST: lbl.set_color(HI); lbl.set_fontweight("medium")
ax.set_xlabel("Prompt (input) tokens per call"); ax.grid(axis="x",color=GRID,lw=0.8); ax.set_axisbelow(True)
ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v,_: f"{v:,.0f}"))
fig.subplots_adjust(left=0.2,right=0.98,top=0.82,bottom=0.13)
save(fig,"03_prompt_size_distribution_1D","Strip plot of prompt sizes for 400 sampled calls per team on a log scale. Medians: "+"; ".join(f"{t} {meds[t]:,.0f}" for t in TEAMS)+".")

# 04 fingerprints (2D small multiples, real)
rows=[]
for t in TEAMS:
    g=R[R.tenant==t]; go=ok[ok.tenant==t]
    rows.append([t,go.input_tokens.median(),g.model.isin(PREMIUM).mean()*100,(go.cached_tokens>0).mean()*100,(g.status==400).mean()*100,go.tokens.sum()/1e6])
F=pd.DataFrame(rows,columns=["tenant","median_prompt","premium","cache","bad","tokM"]); F.round(1).to_csv(f"{OUT}/04_fingerprints_data.csv",index=False)
cols=[("median_prompt","Median prompt size","{:,.0f}"),("premium","Premium-model calls","{:.0f}%"),("cache","Calls using cache","{:.0f}%"),("bad","Bad-request rate","{:.1f}%"),("tokM","Total tokens","{:.0f}M")]
fig,axs=plt.subplots(1,5,figsize=(13,4.6),sharey=True); title(fig,"Two testing teams share the same costly habits, on both providers","Orange: testing teams. Gray: all other teams.")
ypos=[0.9,1.9,2.9,4.5,5.5,6.5]
for j,(c,lab,fmt) in enumerate(cols):
    ax=axs[j]; mx=F[c].max()
    for yi,(_,r) in zip(ypos,F.iterrows()):
        ax.barh(yi,r[c],height=0.62,color=HI if r.tenant in TEST else CTX); ax.text(r[c]+mx*0.03,yi,fmt.format(r[c]),va="center",fontsize=9.5)
    ax.set_xlim(0,mx*1.5); ax.set_title(lab,fontsize=11,fontweight="medium",loc="left"); ax.spines["bottom"].set_visible(False); ax.set_xticks([])
    if j: ax.spines["left"].set_visible(False); ax.tick_params(left=False)
axs[0].set_yticks(ypos); axs[0].set_yticklabels(F.tenant,fontsize=10); axs[0].set_ylim(7.0,-0.3)
for yy,l in [(0.1,"OpenAI teams"),(3.7,"Gemini teams")]: axs[0].text(0,yy,l,fontsize=10,color=INK2,fontweight="medium",va="center")
fig.subplots_adjust(left=0.13,right=0.99,top=0.78,bottom=0.03,wspace=0.12)
save(fig,"04_team_fingerprints_2D","Small-multiple bar charts comparing six teams on five measures. The two testing teams have larger median prompts, more premium-model calls, about 5% cache use versus 37 to 44%, about 6% bad requests versus 1%, and the most tokens.")

# 05 rate limits (2D, real)
R["day"]=R.timestamp.dt.normalize(); d=R[R.status==429].groupby(["day","provider"]).size().unstack(fill_value=0)
fig,ax=plt.subplots(figsize=(10,4.4)); title(fig,"Each provider had one rate-limit spike, and both hit production","Calls rejected with HTTP 429 (too many requests) per day")
for p,c in [("OpenAI","#2a78d6"),("Gemini","#1baf7a")]:
    ax.plot(d.index,d[p],color=c,lw=2); ax.text(d.index[-1]+pd.Timedelta(hours=10),d[p].iloc[-1],p,va="center",fontsize=10,color=INK2)
    i=d[p].idxmax(); v=d[p].max(); top=R[(R.status==429)&(R.day==i)&(R.provider==p)].tenant.value_counts()
    ax.scatter([i],[v],s=40,color=c,zorder=3,edgecolor="#fcfcfb",lw=2)
    ax.annotate(f"{i:%b %d}: {v} calls\n{top.iloc[0]/top.sum()*100:.0f}% from {top.index[0]}",(i,v),xytext=(-12 if p=="Gemini" else 12,6),textcoords="offset points",fontsize=9.5,ha="right" if p=="Gemini" else "left",va="bottom")
ax.set_ylim(0,d.max().max()*1.45); ax.grid(axis="y",color=GRID,lw=0.8); ax.set_axisbelow(True); ax.set_ylabel("Rate-limited calls per day")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d")); fig.subplots_adjust(left=0.08,right=0.92,top=0.8,bottom=0.1)
save(fig,"05_rate_limits_daily_2D","Line chart of daily rate-limited calls for OpenAI and Gemini across October. Both hover around 50 to 85 per day, with one spike each: Gemini on October 14 and OpenAI on October 21, mostly from the production teams.")


with open(f"{OUT}/ALT_TEXT.txt","w",encoding="utf-8") as f:
    for k,v in ALT.items(): f.write(f"{k}\n{v}\n\n")
print("done",len(ALT))
