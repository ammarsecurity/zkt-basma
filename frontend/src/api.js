async function errorMessage(response) {
  try {
    const data = await response.json()
    if (typeof data.detail === 'string' && data.detail) return data.detail
  } catch {
    /* response had no json body */
  }
  return 'حدث خطأ غير متوقع'
}

export async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  })
  if (!response.ok) throw new Error(await errorMessage(response))
  if (response.status === 204) return null
  return response.json()
}

export async function downloadLogs(query) {
  const response = await fetch(`/api/logs/export?${query}`)
  if (!response.ok) throw new Error(await errorMessage(response))
  const blob = await response.blob()
  const header = response.headers.get('Content-Disposition') || ''
  const match = /filename\*=UTF-8''([^;]+)/i.exec(header)
  const filename = match ? decodeURIComponent(match[1]) : 'بصمات.xlsx'
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
