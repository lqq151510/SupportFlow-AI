package com.lqq.supportflow.model.application;
import com.lqq.supportflow.model.domain.ModelUrlPolicy; import java.time.Duration; import org.springframework.http.HttpHeaders; import org.springframework.stereotype.Service; import org.springframework.web.reactive.function.client.WebClient;
@Service public class ProbeModelConnectionService {
 private final ModelUrlPolicy urls; private final WebClient client;
 public ProbeModelConnectionService(ModelUrlPolicy urls, WebClient.Builder builder){this.urls=urls;this.client=builder.build();}
 public ProbeResult probe(String baseUrl,String apiKey){ urls.validate(baseUrl); try { Integer status=client.get().uri(baseUrl).header(HttpHeaders.AUTHORIZATION,"Bearer "+apiKey).exchangeToMono(response->reactor.core.publisher.Mono.just(response.statusCode().value())).block(Duration.ofSeconds(10)); return new ProbeResult(status!=null&&status<500,status==null?"no response":"HTTP "+status); } catch(Exception e){return new ProbeResult(false,"connection failed");} }
 public record ProbeResult(boolean reachable,String message) { }
}
