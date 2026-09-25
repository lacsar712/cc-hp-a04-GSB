<script>
  let username = 'processor'
  let password = 'herb123456'
  let token = localStorage.getItem('herb_token') || ''
  let role = localStorage.getItem('herb_role') || ''
  let who = localStorage.getItem('herb_who') || ''
  let rows = []
  let chapters = []
  let herb = '甘草'
  let tempC = 120
  let minutes = 12
  let chapterId = ''
  let newCode = ''
  let newSummary = ''
  let error = ''
  let chapterError = ''
  let chapterMsg = ''

  async function api(path, options = {}) {
    const res = await fetch(path, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data.detail || '请求失败')
    return data
  }

  async function enter() {
    const data = await api('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
    token = data.access_token
    role = data.role
    who = data.username
    localStorage.setItem('herb_token', token)
    localStorage.setItem('herb_role', role)
    localStorage.setItem('herb_who', who)
    await load()
  }

  async function load() {
    const [batchRows, chapterRows] = await Promise.all([
      api('/api/batches'),
      api('/api/chapters'),
    ])
    rows = batchRows
    chapters = chapterRows
  }

  async function save() {
    error = ''
    if (!chapterId) {
      error = '请先从章节簿挑一条药典章节，未挑不能写入'
      return
    }
    try {
      await api('/api/batches', {
        method: 'POST',
        body: JSON.stringify({
          herb,
          chapter_id: Number(chapterId),
          steps: [{ name: '清炒', temp_c: Number(tempC), minutes: Number(minutes) }],
        }),
      })
      await load()
    } catch (err) {
      error = err.message
    }
  }

  async function addChapter() {
    chapterError = ''
    chapterMsg = ''
    try {
      await api('/api/chapters', {
        method: 'POST',
        body: JSON.stringify({ code: newCode, summary: newSummary }),
      })
      newCode = ''
      newSummary = ''
      chapterMsg = '已录入章节簿'
      await load()
    } catch (err) {
      chapterError = err.message
    }
  }

  async function removeChapter(id) {
    chapterError = ''
    chapterMsg = ''
    try {
      await api(`/api/chapters/${id}`, { method: 'DELETE' })
      if (String(chapterId) === String(id)) chapterId = ''
      chapterMsg = '已从章节簿删除，历史文书仍保留当时引用的章节号与摘要'
      await load()
    } catch (err) {
      chapterError = err.message
    }
  }

  function leave() {
    localStorage.clear()
    token = ''
    role = ''
    who = ''
  }

  if (token) load()
</script>

<main>
  <h1>饮片炮制记录台</h1>
  {#if !token}
    <p>炮制记录整包保存。清炒温度须在 80 到 150，时长须在 5 到 30 分钟。每次写入必须挂一条药典章节。</p>
    <input bind:value={username} />
    <input type="password" bind:value={password} />
    <button on:click={enter}>登录</button>
    <p>processor / herb123456 可写；checker / check123456 只读</p>
  {:else}
    <header class="topbar">
      <span class="brand">饮片炮制记录台</span>
      <nav>
        <a href="#chapters">药典章节引用簿</a>
        <a href="#docs">已引用文书</a>
      </nav>
      <span class="who">{who} · {role === 'writer' ? '炮制员' : '质检员（只读）'}</span>
      <button on:click={leave}>退出</button>
    </header>

    <section id="chapters">
      <h2>药典章节引用簿</h2>
      <p class="hint">每次写入文书必须挑一条已录入章节；章节号与摘要随文书存档，删除章节不影响历史文书。</p>
      {#if chapters.length === 0}
        <p class="hint">章节簿为空。</p>
      {:else}
        <table>
          <thead>
            <tr><th>章节号</th><th>摘要句</th><th>录入人</th>{#if role === 'writer'}<th>操作</th>{/if}</tr>
          </thead>
          <tbody>
            {#each chapters as c (c.id)}
              <tr>
                <td class="code">{c.code}</td>
                <td>{c.summary}</td>
                <td>{c.created_by}</td>
                {#if role === 'writer'}
                  <td><button class="danger" on:click={() => removeChapter(c.id)}>删除</button></td>
                {/if}
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
      {#if role === 'writer'}
        <div class="entry">
          <h3>录入章节</h3>
          <input bind:value={newCode} placeholder="章节号，如 通则0213" />
          <input class="wide" bind:value={newSummary} placeholder="摘要句" />
          <button on:click={addChapter}>录入章节簿</button>
        </div>
      {/if}
      {#if chapterError}<p class="err">{chapterError}</p>{/if}
      {#if chapterMsg}<p class="ok">{chapterMsg}</p>{/if}
    </section>

    {#if role === 'writer'}
      <section id="write">
        <h2>写入炮制文书</h2>
        <input bind:value={herb} placeholder="饮片" />
        <input type="number" bind:value={tempC} />
        <input type="number" bind:value={minutes} />
        <select bind:value={chapterId}>
          <option value="" disabled>请挑一条药典章节（必选）</option>
          {#each chapters as c (c.id)}
            <option value={c.id}>{c.code} · {c.summary}</option>
          {/each}
        </select>
        <button on:click={save}>写入清炒记录</button>
        {#if chapters.length === 0}
          <p class="hint">章节簿为空，请先在上方录入章节，否则无法写入。</p>
        {/if}
        {#if error}<p class="err">{error}</p>{/if}
      </section>
    {/if}

    <section id="docs">
      <h2>已引用文书一览</h2>
      <ul>
        {#each rows as row (row.id)}
          <li>
            <strong>{row.herb}</strong> · {row.verdict} · {row.reason} · 温度 {row.doc.steps[0].temp_c}
            <br />
            {#if row.chapter_code}
              引用章节：<span class="code">{row.chapter_code}</span>（{row.chapter_summary}）
            {:else}
              引用章节：未挂章节（旧文书）
            {/if}
          </li>
        {/each}
      </ul>
    </section>
  {/if}
</main>

<style>
  main { font-family: sans-serif; max-width: 880px; margin: 24px auto; color: #3f2f1f; }
  h1 { color: #7c2d12; }
  h2 { color: #7c2d12; border-bottom: 2px solid #e7d9c4; padding-bottom: 4px; }
  input { margin-right: 8px; padding: 6px; }
  input.wide { width: 320px; }
  select { padding: 6px; margin-right: 8px; max-width: 360px; }
  button { padding: 6px 12px; cursor: pointer; }
  button.danger { color: #b91c1c; }
  section { margin-bottom: 32px; }
  .topbar {
    position: sticky; top: 0; z-index: 1;
    display: flex; align-items: center; gap: 16px;
    background: #f7efe3; border: 1px solid #e7d9c4; border-radius: 8px;
    padding: 10px 16px; margin-bottom: 24px;
  }
  .topbar .brand { font-weight: bold; color: #7c2d12; }
  .topbar nav { display: flex; gap: 12px; flex: 1; }
  .topbar a { color: #9a3412; }
  .topbar .who { color: #78716c; font-size: 14px; }
  table { border-collapse: collapse; width: 100%; margin: 8px 0 16px; }
  th, td { border: 1px solid #e7d9c4; padding: 6px 10px; text-align: left; }
  th { background: #f7efe3; }
  .code { font-family: monospace; font-weight: bold; }
  .entry { background: #faf6ee; border: 1px dashed #d6c7ae; border-radius: 8px; padding: 12px 16px; }
  .entry h3 { margin-top: 0; }
  .hint { color: #78716c; font-size: 14px; }
  .err { color: #b91c1c; }
  .ok { color: #15803d; }
  ul { padding-left: 20px; }
  li { margin-bottom: 10px; line-height: 1.5; }
</style>
