// Custom 1KB-buffered HTTP client for runtime-smol-1kb feature
// Matches Python httpx's 1KB buffer size (vs reqwest's 8KB default)
// Tests the hypothesis that smaller buffers improve streaming latency

use anyhow::{Context, Result};
use bytes::Bytes;
use futures_util::Stream;
use futures_util::StreamExt;
use serde::Serialize;
use std::pin::Pin;

const CHUNK_SIZE_1KB: usize = 1024;

type BoxedByteStream = Pin<Box<dyn Stream<Item = Result<Bytes, reqwest::Error>> + Send>>;

/// 1KB-buffered HTTP client wrapper
/// Uses reqwest but forces 1KB read chunks (vs default 8KB)
#[derive(Clone)]
pub struct Http1KBClient {
    inner: reqwest::Client,
}

impl Http1KBClient {
    pub fn new() -> Result<Self> {
        Ok(Self {
            inner: reqwest::Client::builder()
                .timeout(std::time::Duration::from_secs(300))
                .build()?,
        })
    }

    pub async fn post_streaming<T: Serialize>(
        &self,
        url: &str,
        body: &T,
    ) -> Result<BytesStream1KB> {
        let resp = self
            .inner
            .post(url)
            .json(body)
            .send()
            .await
            .with_context(|| format!("Failed to reach {}", url))?;

        if !resp.status().is_success() {
            anyhow::bail!("HTTP error: {}", resp.status());
        }

        Ok(BytesStream1KB {
            inner: Box::pin(resp.bytes_stream()),
            buffer: Vec::with_capacity(CHUNK_SIZE_1KB * 2),
        })
    }
}

/// Stream that yields 1KB chunks (accumulated from smaller network chunks)
pub struct BytesStream1KB {
    inner: BoxedByteStream,
    buffer: Vec<u8>,
}

impl BytesStream1KB {
    /// Get the next ~1KB chunk
    pub async fn next_chunk(&mut self) -> Option<Result<Bytes>> {
        loop {
            // If buffer >= 1KB, yield it
            if self.buffer.len() >= CHUNK_SIZE_1KB {
                let chunk = Bytes::from(std::mem::take(&mut self.buffer));
                self.buffer = Vec::with_capacity(CHUNK_SIZE_1KB * 2);
                return Some(Ok(chunk));
            }

            // Read more data from network
            match self.inner.next().await {
                Some(Ok(bytes)) => {
                    self.buffer.extend_from_slice(&bytes);
                    // Continue accumulating
                }
                Some(Err(e)) => {
                    return Some(Err(e.into()));
                }
                None => {
                    // End of stream - yield remaining buffer if any
                    if !self.buffer.is_empty() {
                        let chunk = Bytes::from(std::mem::take(&mut self.buffer));
                        return Some(Ok(chunk));
                    }
                    return None;
                }
            }
        }
    }
}
