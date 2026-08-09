package com.lqq.supportflow.ticket.domain;

import com.lqq.supportflow.ticket.SlaDeadline;
import java.time.Instant;
import java.util.List;

public interface SlaMonitorPort {
    List<SlaDeadline> dueAt(Instant now);
    boolean markAlerted(SlaDeadline deadline);
}
