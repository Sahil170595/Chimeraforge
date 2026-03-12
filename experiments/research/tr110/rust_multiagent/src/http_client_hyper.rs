// Hyper-based HTTP client for smol runtime
// Uses standard chunk size (matches reqwest's default ~8KB buffering)

use anyhow::{Context, Result};
use bytes::Bytes;
use futures_util::Stream;
use http_body_util::{BodyExt, Full};
use hyper::body::Incoming;
use hyper::{Method, Request, StatusCode};
use hyper_util::client::legacy::Client;
use hyper_util::rt::TokioExecutor;
use serde::Serialize;
use std::pin::Pin;
use std::task::{Context as TaskContext, Poll};

pub struct HyperClient {
    client: Client<hyper_util::client::legacy::connect::HttpConnector, Full<Bytes>>,
}

impl HyperClient {
    pub fn new() -> Result<Self> {
        let client = Client::builder(TokioExecutor::new()).build_http();
        Ok(Self { client })
    }

    pub async fn post_streaming<T: Serialize>(
        &self,
        url: &str,
        body: &T,
    ) -> Result<BytesStream> {
        let json_body = serde_json::to_vec(body).context("Failed to serialize request body")?;

        let req = Request::builder()
            .method(Method::POST)
            .uri(url)
            .header("Content-Type", "application/json")
            .body(Full::new(Bytes::from(json_body)))
            .context("Failed to build HTTP request")?;

        let resp = self
            .client
            .request(req)
            .await
            .context("HTTP request failed")?;

        if resp.status() != StatusCode::OK {
            anyhow::bail!("HTTP error: {}", resp.status());
        }

        let body = resp.into_body();
        Ok(BytesStream { inner: body })
    }
}

pub struct BytesStream {
    inner: Incoming,
}

impl Stream for BytesStream {
    type Item = Result<Bytes, hyper::Error>;

    fn poll_next(
        mut self: Pin<&mut Self>,
        cx: &mut TaskContext<'_>,
    ) -> Poll<Option<Self::Item>> {
        match Pin::new(&mut self.inner).poll_frame(cx) {
            Poll::Ready(Some(Ok(frame))) => {
                if let Ok(data) = frame.into_data() {
                    Poll::Ready(Some(Ok(data)))
                } else {
                    // Non-data frame, continue polling
                    self.poll_next(cx)
                }
            }
            Poll::Ready(Some(Err(e))) => Poll::Ready(Some(Err(e))),
            Poll::Ready(None) => Poll::Ready(None),
            Poll::Pending => Poll::Pending,
        }
    }
}

