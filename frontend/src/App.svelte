<script>
  let username = 'processor'
  let password = 'herb123456'
  let token = localStorage.getItem('herb_token') || ''
  let role = localStorage.getItem('herb_role') || ''
  let rows = []
  let chapters = []
  let herb = '甘草'
  let tempC = 110
  let minutes = 10
  let chapterId = ''
  let newNo = ''
  let newSummary = ''
  let error = ''
  let chapterError = ''
  let loginError = ''

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
    loginError = ''
    try {
      const data = await api('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      })
      token = data.access_token
      role = data.role
      localStorage.setItem('herb_token', token)
      localStorage.setItem('herb_role', role)
      await load()
    } catch (err) {
      loginError = err.message
    }
  }

  async function load() {
    const [b, c] = await Promise.all([api('/api/batches'), api('/api/chapters')])
    rows = b
    chapters = c
    if (chapterId && !chapters.some((c) => String(c.id) === String(chapterId))) chapterId = ''
  }

  async function save() {
    error = ''
    if (!chapterId) {
      error = '未挑章节，拒写：请先从章节簿选择一条已录入的药典章节'
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
    if (!newNo.trim() || !newSummary.trim()) {
      chapterError = '章节号与摘要句均须填写'
      return
    }
    try {
      await api('/api/chapters', {
        method: 'POST',
        body: JSON.stringify({ chapter_no: newNo.trim(), summary: newSummary.trim() }),
      })
      newNo = ''
      newSummary = ''
      await load()
    } catch (err) {
      chapterError = err.message
    }
  }

  async function removeChapter(id) {
    chapterError = ''
    try {
      await api(`/api/chapters/${id}`, { method: 'DELETE' })
      await load()
    } catch (err) {
      chapterError = err.message
    }
  }

  function leave() {
    localStorage.clear()
    token = ''
    role = ''
  }

  if (token) load()
</script>

{#if !token}
  <main class="narrow">
    <h1>饮片炮制记录台</h1>
    <p>炮制记录整包保存，每包文书必须引用一条药典章节。清炒温度须在 80 到 150，时长须在 5 到 30 分钟。</p>
    <div class="login">
      <input bind:value={username} placeholder="用户名" />
      <input type="password" bind:value={password} placeholder="密码" />
      <button on:click={enter}>登录</button>
    </div>
    {#if loginError}<p class="err">{loginError}</p>{/if}
    <p class="hint">processor / herb123456 可写；checker / check123456 只读</p>
  </main>
{:else}
  <header class="topbar">
    <span class="brand">饮片炮制记录台</span>
    <nav>
      <a href="#entry">录入区</a>
      <a href="#chapters">章节引用</a>
      <a href="#docs">已引用文书</a>
    </nav>
    <span class="who">{username} · {role === 'writer' ? '炮制员' : '质检员（只读）'}</span>
    <button class="link" on:click={leave}>退出</button>
  </header>

  <main>
    <section id="entry" class="card">
      <h2>录入区 · 写炮制文书</h2>
      {#if role === 'writer'}
        <div class="formrow">
          <label>饮片 <input bind:value={herb} placeholder="饮片" /></label>
          <label>清炒温度℃ <input type="number" bind:value={tempC} /></label>
          <label>时长（分） <input type="number" bind:value={minutes} /></label>
        </div>
        <div class="formrow">
          <label class="grow">引用药典章节（必选）
            <select bind:value={chapterId}>
              <option value="" disabled>请从章节簿挑选一条已录入章节</option>
              {#each chapters as c}
                <option value={c.id}>{c.chapter_no} · {c.summary}</option>
              {/each}
            </select>
          </label>
          <button class="primary" on:click={save}>写入清炒记录</button>
        </div>
        {#if chapters.length === 0}
          <p class="hint">章节簿为空，请先在下方「章节引用」录入章节，否则无法写入。</p>
        {/if}
        {#if error}<p class="err">{error}</p>{/if}
      {:else}
        <p class="hint">质检员仅可查看，不可写入文书。</p>
      {/if}
    </section>

    <section id="chapters" class="card">
      <h2>章节引用 · 药典章节簿</h2>
      {#if role === 'writer'}
        <div class="formrow">
          <label>章节号 <input bind:value={newNo} placeholder="如 通则0213" /></label>
          <label class="grow">摘要句 <input bind:value={newSummary} placeholder="如 炮制通则：清炒温度与时长须受控" /></label>
          <button class="primary" on:click={addChapter}>录入章节</button>
        </div>
        {#if chapterError}<p class="err">{chapterError}</p>{/if}
      {:else}
        <p class="hint">质检员仅可查看章节簿，不可录入或删除。</p>
      {/if}
      <table>
        <thead>
          <tr><th>章节号</th><th>摘要句</th><th>录入人</th>{#if role === 'writer'}<th>操作</th>{/if}</tr>
        </thead>
        <tbody>
          {#each chapters as c}
            <tr>
              <td class="no">{c.chapter_no}</td>
              <td>{c.summary}</td>
              <td>{c.created_by}</td>
              {#if role === 'writer'}
                <td><button class="danger" on:click={() => removeChapter(c.id)}>删除</button></td>
              {/if}
            </tr>
          {:else}
            <tr><td colspan="4" class="hint">章节簿暂无条目</td></tr>
          {/each}
        </tbody>
      </table>
    </section>

    <section id="docs" class="card">
      <h2>已引用文书一览</h2>
      <table>
        <thead>
          <tr><th>饮片</th><th>结论</th><th>原因</th><th>温度℃</th><th>引用章节号</th><th>章节摘要</th></tr>
        </thead>
        <tbody>
          {#each rows as row}
            <tr>
              <td>{row.herb}</td>
              <td class={row.verdict === '放行' ? 'ok' : 'bad'}>{row.verdict}</td>
              <td>{row.reason}</td>
              <td>{row.doc.steps[0].temp_c}</td>
              {#if row.chapter_no}
                <td class="no">{row.chapter_no}</td>
                <td>{row.chapter_summary}</td>
              {:else}
                <td colspan="2" class="hint">—（章节簿建立前的旧文书）</td>
              {/if}
            </tr>
          {:else}
            <tr><td colspan="6" class="hint">暂无文书</td></tr>
          {/each}
        </tbody>
      </table>
    </section>
  </main>
{/if}

<style>
  :global(body) { margin: 0; background: #faf6ef; }
  main { font-family: sans-serif; max-width: 880px; margin: 24px auto; padding: 0 16px; color: #3f2f1f; }
  main.narrow { max-width: 560px; }
  h1 { color: #7c2d12; }
  h2 { color: #7c2d12; font-size: 18px; margin: 0 0 12px; }
  .topbar {
    position: sticky; top: 0; z-index: 1;
    display: flex; align-items: center; gap: 20px;
    background: #7c2d12; color: #fde8d8; padding: 10px 20px;
    font-family: sans-serif;
  }
  .brand { font-weight: 700; }
  .topbar nav { display: flex; gap: 14px; flex: 1; }
  .topbar a { color: #ffd9b3; text-decoration: none; }
  .topbar a:hover { text-decoration: underline; }
  .who { font-size: 13px; }
  .card { background: #fff; border: 1px solid #e8dcc8; border-radius: 8px; padding: 16px 18px; margin-bottom: 20px; }
  .formrow { display: flex; align-items: flex-end; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }
  .formrow label { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: #6b543c; }
  .grow { flex: 1; min-width: 220px; }
  input, select { padding: 6px 8px; border: 1px solid #cbb894; border-radius: 4px; font-size: 14px; }
  .login input { margin-right: 8px; }
  button { padding: 7px 14px; border: 1px solid #a87f4f; border-radius: 4px; background: #f3e7d3; color: #5c3a17; cursor: pointer; }
  button.primary { background: #b3541e; border-color: #b3541e; color: #fff; }
  button.danger { background: #fdecec; border-color: #c0392b; color: #c0392b; padding: 4px 10px; }
  button.link { background: none; border: none; color: #ffd9b3; text-decoration: underline; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th, td { text-align: left; padding: 7px 8px; border-bottom: 1px solid #eee2cd; vertical-align: top; }
  th { color: #8a6a45; font-weight: 600; }
  .no { font-weight: 700; white-space: nowrap; }
  .ok { color: #1e7e34; font-weight: 700; }
  .bad { color: #c0392b; font-weight: 700; }
  .err { color: #c0392b; }
  .hint { color: #9a8264; font-size: 13px; }
</style>
