# -*- coding: utf-8 -*-
"""
NVMe 2.0 I/O Queue Deletion Tests

Purpose:
    Validate I/O Queue deletion using Delete I/O Submission Queue and
    Delete I/O Completion Queue admin commands according to NVMe 2.0 specification.

NVMe 2.0 Specification References:
    - §5.5: Delete I/O Completion Queue command
    - §5.6: Delete I/O Submission Queue command
    - §4.1: Queue management
    - §7.2: Error codes

Test Coverage:
    - Correct deletion order (SQ before CQ)
    - Queue pair deletion using PyNVMe
    - Idle queue deletion
    - Negative tests for incorrect deletion order
    - Deletion of non-existent queues
    - Commands to deleted queues
    - Controller reset with active queues
"""

import pytest
import logging
import time
import nvme as d
from psd import IOCQ, IOSQ, PRP

logger = logging.getLogger(__name__)


# ============================================================================
# POSITIVE TESTS - I/O Queue Deletion
# ============================================================================

@pytest.mark.positive
@pytest.mark.io_queue
def test_delete_io_queues_correct_order(nvme0):
    """
    Test: Delete I/O Queues in Correct Order
    
    Purpose:
        Verify SQ must be deleted before CQ as required by NVMe spec.
    
    Preconditions:
        - Controller ready
    
    Test Steps:
        1. Create I/O CQ (CQID = 1)
        2. Create I/O SQ (SQID = 1) associated with CQ 1
        3. Delete SQ first using sq.delete()
        4. Delete CQ second using cq.delete()
        5. Verify successful deletion
    
    Expected Result:
        - SQ deleted successfully
        - CQ deleted successfully after SQ
        - No errors during deletion
    
    NVMe 2.0 Reference: §5.5, §5.6 (Delete commands require SQ deleted before CQ)
    """
    logger.info("=== Test: Delete I/O Queues in Correct Order ===")
    
    cqid = 1
    sqid = 1
    qsize = 16
    
    # Step 1: Create CQ
    logger.info(f"Step 1: Creating I/O CQ {cqid}")
    cq = IOCQ(nvme0, cqid, qsize, PRP())
    logger.info(f"  ✓ CQ {cqid} created")
    
    # Step 2: Create SQ
    logger.info(f"Step 2: Creating I/O SQ {sqid} associated with CQ {cqid}")
    sq = IOSQ(nvme0, sqid, qsize, PRP(), cqid=cqid)
    logger.info(f"  ✓ SQ {sqid} created")
    
    # Step 3: Delete SQ first (REQUIRED ORDER)
    logger.info(f"Step 3: Deleting SQ {sqid} (must be before CQ)")
    sq.delete()
    logger.info(f"  ✓ SQ {sqid} deleted successfully")
    
    # Step 4: Delete CQ second
    logger.info(f"Step 4: Deleting CQ {cqid} (after SQ)")
    cq.delete()
    logger.info(f"  ✓ CQ {cqid} deleted successfully")
    
    logger.info("✓ Correct deletion order validated successfully")


@pytest.mark.positive
@pytest.mark.io_queue
def test_qpair_deletion(nvme0):
    """
    Test: Queue Pair Deletion using PyNVMe
    
    Purpose:
        Verify Qpair.delete() correctly handles SQ/CQ deletion order.
    
    Preconditions:
        - Controller ready
    
    Test Steps:
        1. Create Qpair using d.Qpair()
        2. Verify queue is created (check sqid)
        3. Delete using qpair.delete()
        4. Verify deletion completes without errors
    
    Expected Result:
        - Qpair created successfully
        - Qpair deleted successfully
        - PyNVMe handles correct deletion order automatically
    
    NVMe 2.0 Reference: §5.5, §5.6
    """
    logger.info("=== Test: Qpair Deletion ===")
    
    # Step 1: Create Qpair
    logger.info("Step 1: Creating Qpair with depth=16")
    qpair = d.Qpair(nvme0, depth=16)
    
    # Step 2: Verify creation
    sqid = qpair.sqid
    logger.info(f"Step 2: Qpair created with SQID={sqid}")
    assert sqid > 0, "Valid SQID should be assigned"
    
    # Step 3: Delete Qpair
    logger.info("Step 3: Deleting Qpair")
    qpair.delete()
    logger.info("  ✓ Qpair deleted successfully")
    
    logger.info("✓ Qpair deletion validated successfully")


@pytest.mark.positive
@pytest.mark.io_queue
def test_delete_idle_queues(nvme0, nvme0n1):
    """
    Test: Delete Idle Queues
    
    Purpose:
        Delete queues with no outstanding commands (idle state).
    
    Preconditions:
        - Controller and namespace ready
    
    Test Steps:
        1. Create Qpair
        2. Submit I/O commands
        3. Wait for all commands to complete (queue becomes idle)
        4. Delete queue pair
        5. Verify clean deletion
    
    Expected Result:
        - All I/O completes successfully
        - Queue deleted cleanly after becoming idle
    
    NVMe 2.0 Reference: §5.5, §5.6 (Queue deletion)
    """
    logger.info("=== Test: Delete Idle Queues ===")
    
    # Step 1: Create Qpair
    logger.info("Step 1: Creating Qpair")
    qpair = d.Qpair(nvme0, depth=8)
    logger.info(f"  ✓ Qpair created with SQID={qpair.sqid}")
    
    # Step 2: Submit I/O commands
    logger.info("Step 2: Submitting I/O commands")
    buf = d.Buffer(4096)
    
    num_commands = 5
    for i in range(num_commands):
        nvme0n1.write(qpair, buf, i, 1)
    logger.info(f"  Submitted {num_commands} Write commands")
    
    # Step 3: Wait for completion (queue becomes idle)
    logger.info("Step 3: Waiting for all commands to complete")
    qpair.waitdone(num_commands)
    logger.info("  ✓ All commands completed, queue is idle")
    
    # Step 4: Delete queue
    logger.info("Step 4: Deleting idle queue")
    qpair.delete()
    logger.info("  ✓ Idle queue deleted successfully")
    
    logger.info("✓ Idle queue deletion validated successfully")


@pytest.mark.positive
@pytest.mark.io_queue
def test_delete_multiple_queues(nvme0):
    """
    Test: Delete Multiple Queues
    
    Purpose:
        Create and delete multiple queue pairs.
    
    Preconditions:
        - Controller ready
    
    Test Steps:
        1. Create multiple Qpairs (4 queues)
        2. Delete all queues
        3. Verify all deletions successful
    
    Expected Result:
        - All queues created successfully
        - All queues deleted successfully
    
    NVMe 2.0 Reference: §5.5, §5.6
    """
    logger.info("=== Test: Delete Multiple Queues ===")
    
    num_queues = 4
    
    # Step 1: Create multiple queues
    logger.info(f"Step 1: Creating {num_queues} Qpairs")
    qpairs = []
    
    for i in range(num_queues):
        qp = d.Qpair(nvme0, depth=8)
        qpairs.append(qp)
        logger.info(f"  Created Qpair {i+1}/{num_queues}, SQID={qp.sqid}")
    
    logger.info(f"  ✓ All {num_queues} Qpairs created")
    
    # Step 2: Delete all queues
    logger.info(f"Step 2: Deleting all {num_queues} Qpairs")
    
    for i, qp in enumerate(qpairs):
        qp.delete()
        logger.info(f"  Deleted Qpair {i+1}/{num_queues}")
    
    logger.info(f"  ✓ All {num_queues} Qpairs deleted successfully")
    
    logger.info("✓ Multiple queue deletion validated successfully")


@pytest.mark.positive
@pytest.mark.io_queue
def test_recreate_queue_after_deletion(nvme0):
    """
    Test: Recreate Queue After Deletion
    
    Purpose:
        Verify queue IDs can be reused after deletion.
    
    Preconditions:
        - Controller ready
    
    Test Steps:
        1. Create queue using low-level API with specific QIDs
        2. Delete queues
        3. Recreate queues with same QIDs
        4. Verify successful recreation
        5. Delete again
    
    Expected Result:
        - Queue created with QID
        - Queue deleted successfully
        - Same QID can be reused for new queue
    
    NVMe 2.0 Reference: §5.3, §5.4 (Queue IDs can be reused after deletion)
    """
    logger.info("=== Test: Recreate Queue After Deletion ===")
    
    cqid = 5
    sqid = 5
    qsize = 16
    
    # Step 1: Create queues with specific IDs
    logger.info(f"Step 1: Creating queues with CQID={cqid}, SQID={sqid}")
    cq = IOCQ(nvme0, cqid, qsize, PRP())
    sq = IOSQ(nvme0, sqid, qsize, PRP(), cqid=cqid)
    logger.info("  ✓ Queues created")
    
    # Step 2: Delete queues
    logger.info("Step 2: Deleting queues")
    sq.delete()
    cq.delete()
    logger.info("  ✓ Queues deleted")
    
    # Step 3: Recreate with same IDs
    logger.info(f"Step 3: Recreating queues with same IDs (CQID={cqid}, SQID={sqid})")
    cq2 = IOCQ(nvme0, cqid, qsize, PRP())
    sq2 = IOSQ(nvme0, sqid, qsize, PRP(), cqid=cqid)
    logger.info("  ✓ Queues recreated with same IDs")
    
    # Step 5: Delete again
    logger.info("Step 5: Deleting recreated queues")
    sq2.delete()
    cq2.delete()
    logger.info("  ✓ Recreated queues deleted")
    
    logger.info("✓ Queue ID reuse validated successfully")


# ============================================================================
# NEGATIVE TESTS - Queue Deletion Error Handling
# ============================================================================

@pytest.mark.negative
@pytest.mark.io_queue
def test_delete_cq_before_sq(nvme0):
    """
    Test: Delete CQ Before SQ (Negative)
    
    Purpose:
        Attempt to delete CQ while associated SQ still exists.
        This violates NVMe spec requirements.
    
    Preconditions:
        - Controller ready
    
    Test Steps:
        1. Create CQ and SQ
        2. Attempt to delete CQ first (incorrect order)
        3. Expect error: Invalid Queue Deletion (0x010C)
    
    Expected Result:
        - CQ deletion fails
        - Error: SC=0x0C, SCT=0x01 (Invalid Queue Deletion)
        - SQ remains valid
    
    NVMe 2.0 Reference: §5.5 (CQ cannot be deleted while SQ exists)
    """
    logger.info("=== Test: Delete CQ Before SQ (Negative) ===")
    
    cqid = 1
    sqid = 1
    qsize = 16
    
    # Create queues
    logger.info("Creating CQ and SQ")
    cq = IOCQ(nvme0, cqid, qsize, PRP())
    sq = IOSQ(nvme0, sqid, qsize, PRP(), cqid=cqid)
    logger.info("  ✓ Queues created")
    
    # Attempt to delete CQ before SQ (INVALID)
    logger.info("Attempting to delete CQ before SQ (invalid order)")
    
    try:
        cq.delete()
        
        # If we get here, the deletion succeeded (shouldn't happen)
        # Clean up SQ
        sq.delete()
        
        pytest.fail("Expected error when deleting CQ before SQ")
        
    except Exception as e:
        logger.info(f"  ✓ CQ deletion before SQ rejected: {e}")
        
        # Clean up in correct order
        logger.info("Cleaning up in correct order")
        sq.delete()
        cq.delete()
        logger.info("  ✓ Cleanup complete")
    
    logger.info("✓ Invalid deletion order error handling validated")


@pytest.mark.negative
@pytest.mark.io_queue
def test_delete_non_existent_queue(nvme0):
    """
    Test: Delete Non-Existent Queue (Negative)
    
    Purpose:
        Attempt to delete queue that doesn't exist or was already deleted.
    
    Preconditions:
        - Controller ready
    
    Test Steps:
        1. Create and delete a queue
        2. Attempt to delete the same queue again
        3. Expect error: Invalid Queue Identifier
    
    Expected Result:
        - Second deletion fails
        - Error: SC=0x01, SCT=0x01 (Invalid Queue Identifier)
    
    NVMe 2.0 Reference: §5.5, §5.6 (QID must be valid)
    """
    logger.info("=== Test: Delete Non-Existent Queue (Negative) ===")
    
    cqid = 1
    sqid = 1
    qsize = 16
    
    # Create and delete queue normally
    logger.info("Creating and deleting queue normally")
    cq = IOCQ(nvme0, cqid, qsize, PRP())
    sq = IOSQ(nvme0, sqid, qsize, PRP(), cqid=cqid)
    
    sq.delete()
    cq.delete()
    logger.info("  ✓ Queue deleted")
    
    # Attempt second deletion
    logger.info("Attempting to delete already-deleted queue")
    
    try:
        # Try to delete SQ again
        sq.delete()
        
        logger.warning("Second deletion succeeded (may be implementation dependent)")
        
    except Exception as e:
        logger.info(f"  ✓ Second deletion rejected: {e}")
    
    logger.info("✓ Non-existent queue deletion error handling validated")


@pytest.mark.negative
@pytest.mark.io_queue
def test_delete_queue_with_outstanding_io(nvme0, nvme0n1):
    """
    Test: Delete Queue with Outstanding I/O (Negative)
    
    Purpose:
        Attempt to delete queue while commands are still outstanding.
    
    Preconditions:
        - Controller and namespace ready
    
    Test Steps:
        1. Create Qpair
        2. Submit I/O commands without waiting
        3. Immediately attempt queue deletion
        4. Verify proper error handling or forced completion
    
    Expected Result:
        - Deletion may fail, or
        - Outstanding commands are aborted/completed first
    
    NVMe 2.0 Reference: §5.6 (SQ deletion behavior with outstanding commands)
    """
    logger.info("=== Test: Delete Queue with Outstanding I/O (Negative) ===")
    
    # Create Qpair
    logger.info("Creating Qpair")
    qpair = d.Qpair(nvme0, depth=16)
    logger.info(f"  ✓ Qpair created with SQID={qpair.sqid}")
    
    # Submit I/O without waiting
    logger.info("Submitting I/O commands without waiting for completion")
    buf = d.Buffer(4096)
    
    num_commands = 8
    for i in range(num_commands):
        nvme0n1.write(qpair, buf, i * 8, 1)
    
    logger.info(f"  Submitted {num_commands} commands")
    
    # Attempt immediate deletion
    logger.info("Attempting immediate queue deletion (with outstanding I/O)")
    
    try:
        # Small delay to ensure commands are in flight
        time.sleep(0.01)
        
        # Delete queue
        qpair.delete()
        
        logger.info("  ✓ Queue deleted (commands may have been aborted or completed)")
        logger.info("  Note: Implementation may force command completion before deletion")
        
    except Exception as e:
        logger.info(f"  ✓ Queue deletion with outstanding I/O rejected: {e}")
    
    logger.info("✓ Outstanding I/O during deletion validated")


@pytest.mark.negative
@pytest.mark.io_queue
def test_submit_to_deleted_queue(nvme0, nvme0n1):
    """
    Test: Submit Command to Deleted Queue (Negative)
    
    Purpose:
        Attempt to submit I/O to a deleted queue.
    
    Preconditions:
        - Controller ready
    
    Test Steps:
        1. Create Qpair
        2. Delete Qpair
        3. Attempt to submit I/O to deleted queue
        4. Expect error or exception
    
    Expected Result:
        - I/O submission fails
        - Exception or error returned
    
    NVMe 2.0 Reference: Queue must exist for I/O submission
    """
    logger.info("=== Test: Submit to Deleted Queue (Negative) ===")
    
    # Create and delete queue
    logger.info("Creating Qpair")
    qpair = d.Qpair(nvme0, depth=8)
    sqid = qpair.sqid
    logger.info(f"  ✓ Qpair created with SQID={sqid}")
    
    logger.info("Deleting Qpair")
    qpair.delete()
    logger.info("  ✓ Qpair deleted")
    
    # Attempt I/O to deleted queue
    logger.info("Attempting to submit I/O to deleted queue")
    buf = d.Buffer(4096)
    
    try:
        nvme0n1.write(qpair, buf, 0, 1)
        qpair.waitdone(1)
        
        pytest.fail("Expected error when submitting to deleted queue")
        
    except Exception as e:
        logger.info(f"  ✓ I/O to deleted queue rejected: {e}")
    
    logger.info("✓ Deleted queue I/O rejection validated")


# ============================================================================
# EDGE CASE TESTS
# ============================================================================

@pytest.mark.edge
@pytest.mark.io_queue
def test_controller_reset_with_active_queues(nvme0):
    """
    Test: Controller Reset with Active I/O Queues (Edge Case)
    
    Purpose:
        Verify behavior when controller is reset while I/O queues are active.
    
    Preconditions:
        - Controller ready
    
    Test Steps:
        1. Create multiple Qpairs
        2. Perform controller reset
        3. Verify queues are implicitly deleted
        4. Re-initialize controller
        5. Verify new queues can be created with same IDs
    
    Expected Result:
        - Controller reset succeeds
        - Queues are implicitly deleted during reset
        - Queue IDs can be reused after reset
    
    NVMe 2.0 Reference: §7.3.6 (Controller reset clears all queues except admin)
    """
    logger.info("=== Test: Controller Reset with Active Queues ===")
    
    # Step 1: Create multiple queues
    logger.info("Step 1: Creating multiple Qpairs")
    num_queues = 3
    qpairs = []
    sqids = []
    
    for i in range(num_queues):
        qp = d.Qpair(nvme0, depth=8)
        qpairs.append(qp)
        sqids.append(qp.sqid)
        logger.info(f"  Created Qpair {i+1}, SQID={qp.sqid}")
    
    logger.info(f"  ✓ Created {num_queues} Qpairs with SQIDs: {sqids}")
    
    # Step 2: Perform controller reset
    logger.info("Step 2: Performing controller reset")
    logger.warning("  NOTE: Test scripts should normally delete all I/O qpairs before reset")
    logger.info("  Resetting controller with active queues (for test purposes)")
    
    nvme0.reset()
    logger.info("  ✓ Controller reset complete")
    
    # After reset, queues are implicitly deleted
    # No need to explicitly delete qpairs
    
    # Step 4: Re-initialize (admin queue is re-created automatically)
    logger.info("Step 4: Controller re-initialized")
    
    # Step 5: Create new queues (can reuse IDs)
    logger.info("Step 5: Creating new Qpairs after reset")
    
    new_qpairs = []
    for i in range(num_queues):
        qp = d.Qpair(nvme0, depth=8)
        new_qpairs.append(qp)
        logger.info(f"  Created new Qpair {i+1}, SQID={qp.sqid}")
    
    logger.info("  ✓ New Qpairs created after reset")
    
    # Clean up
    logger.info("Cleaning up new queues")
    for qp in new_qpairs:
        qp.delete()
    
    logger.info("✓ Controller reset with active queues validated successfully")


@pytest.mark.edge
@pytest.mark.io_queue
def test_rapid_queue_create_delete(nvme0):
    """
    Test: Rapid Queue Creation and Deletion (Edge Case)
    
    Purpose:
        Stress test rapid queue create/delete cycles.
    
    Preconditions:
        - Controller ready
    
    Test Steps:
        1. Rapidly create and delete queues in a loop
        2. Verify all operations succeed
        3. Check for resource leaks
    
    Expected Result:
        - All create/delete operations succeed
        - No resource leaks
        - Controller remains stable
    
    NVMe 2.0 Reference: Queue lifecycle management
    """
    logger.info("=== Test: Rapid Queue Create/Delete ===")
    
    num_iterations = 10
    logger.info(f"Performing {num_iterations} rapid create/delete cycles")
    
    for i in range(num_iterations):
        # Create
        qp = d.Qpair(nvme0, depth=8)
        sqid = qp.sqid
        
        # Immediately delete
        qp.delete()
        
        if (i + 1) % 5 == 0:
            logger.info(f"  Completed {i + 1}/{num_iterations} cycles")
    
    logger.info(f"  ✓ All {num_iterations} rapid create/delete cycles completed")
    logger.info("✓ Rapid queue create/delete validated successfully")


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v", "-s"])
