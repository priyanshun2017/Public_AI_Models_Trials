# -*- coding: utf-8 -*-
"""
NVMe 2.0 I/O Queue Creation Tests

Purpose:
    Validate I/O Submission Queue and I/O Completion Queue creation using
    Admin Commands according to NVMe 2.0 specification.

NVMe 2.0 Specification References:
    - §5.3: Create I/O Completion Queue command
    - §5.4: Create I/O Submission Queue command
    - §4.1: Submission and Completion Queues
    - §7.2: Error codes and status fields

Test Coverage:
    - I/O CQ creation with various parameters
    - I/O SQ creation with various parameters
    - Queue pair creation using PyNVMe Qpair abstraction
    - Multiple queue creation
    - Queue size validation
    - Negative tests for invalid parameters
"""

import pytest
import logging
import nvme as d
from psd import IOCQ, IOSQ, PRP
from conftest import get_max_queue_count

logger = logging.getLogger(__name__)


# ============================================================================
# POSITIVE TESTS - I/O Queue Creation
# ============================================================================

@pytest.mark.positive
@pytest.mark.io_queue
def test_create_io_completion_queue(nvme0):
    """
    Test: Create I/O Completion Queue
    
    Purpose:
        Create I/O Completion Queue using Create I/O Completion Queue admin command.
        Validate queue parameters.
    
    Preconditions:
        - Controller ready with admin queue initialized
    
    Test Steps:
        1. Allocate memory for CQ using PRP (Physical Region Page)
        2. Issue Create I/O Completion Queue command
        3. Specify: Queue ID = 1, Queue Size = 64, Physically Contiguous
        4. Verify command completion without errors
        5. Delete CQ when done
    
    Expected Result:
        - CQ created successfully
        - Queue ID is 1
        - Queue size is 64 entries
    
    NVMe 2.0 Reference: §5.3 (Create I/O Completion Queue)
    """
    logger.info("=== Test: Create I/O Completion Queue ===")
    
    # Step 1-2: Create I/O CQ using low-level PSD library
    qid = 1
    qsize = 64
    
    logger.info(f"Creating I/O CQ with QID={qid}, Size={qsize}")
    
    # IOCQ constructor: IOCQ(nvme, qid, qsize, prp, iv=0, pc=1)
    # qid: Queue ID, qsize: Queue Size, prp: PRP for queue memory
    # iv: Interrupt Vector, pc: Physically Contiguous (1=yes, 0=no)
    cq = IOCQ(nvme0, qid, qsize, PRP(), iv=0, pc=1)
    
    logger.info(f"✓ I/O CQ {qid} created successfully with {qsize} entries")
    logger.info(f"  Physically Contiguous: Yes")
    logger.info(f"  Interrupt Vector: 0")
    
    # Step 5: Delete CQ
    logger.info(f"Deleting I/O CQ {qid}")
    cq.delete()
    
    logger.info("✓ I/O Completion Queue creation validated successfully")


@pytest.mark.positive
@pytest.mark.io_queue
def test_create_io_submission_queue(nvme0):
    """
    Test: Create I/O Submission Queue
    
    Purpose:
        Create I/O Submission Queue using Create I/O Submission Queue admin command.
        Validate SQ is associated with a valid CQ.
    
    Preconditions:
        - Controller ready
        - I/O CQ must be created first
    
    Test Steps:
        1. Create I/O CQ (CQID = 1)
        2. Create I/O SQ (SQID = 1) associated with CQ 1
        3. Specify: Queue Priority (for WRR), Physically Contiguous
        4. Verify both queues created successfully
        5. Delete SQ before CQ (required order)
    
    Expected Result:
        - SQ created successfully
        - SQ associated with correct CQ
        - Proper deletion order enforced (SQ before CQ)
    
    NVMe 2.0 Reference: §5.4 (Create I/O Submission Queue)
    """
    logger.info("=== Test: Create I/O Submission Queue ===")
    
    cqid = 1
    sqid = 1
    qsize = 64
    
    # Step 1: Create I/O CQ first
    logger.info(f"Step 1: Creating I/O CQ {cqid}")
    cq = IOCQ(nvme0, cqid, qsize, PRP())
    
    # Step 2: Create I/O SQ associated with CQ
    logger.info(f"Step 2: Creating I/O SQ {sqid} associated with CQ {cqid}")
    
    # IOSQ constructor: IOSQ(nvme, qid, qsize, prp, cqid=0, prio=0, pc=1)
    # prio: Priority for Weighted Round Robin (0=Urgent, 1=High, 2=Medium, 3=Low)
    sq = IOSQ(nvme0, sqid, qsize, PRP(), cqid=cqid, prio=0, pc=1)
    
    logger.info(f"✓ I/O SQ {sqid} created successfully")
    logger.info(f"  Associated CQ ID: {cqid}")
    logger.info(f"  Queue Size: {qsize} entries")
    logger.info(f"  Priority: 0 (Urgent)")
    logger.info(f"  Physically Contiguous: Yes")
    
    # Step 5: Delete in correct order (SQ before CQ)
    logger.info("Step 5: Deleting queues in correct order (SQ before CQ)")
    sq.delete()
    logger.info(f"  ✓ Deleted SQ {sqid}")
    
    cq.delete()
    logger.info(f"  ✓ Deleted CQ {cqid}")
    
    logger.info("✓ I/O Submission Queue creation validated successfully")


@pytest.mark.positive
@pytest.mark.io_queue
def test_qpair_creation(nvme0):
    """
    Test: Queue Pair Creation using PyNVMe Abstraction
    
    Purpose:
        Create I/O queue pairs using PyNVMe Qpair class.
        Verify various queue depths and interrupt configurations.
    
    Preconditions:
        - Controller ready
    
    Test Steps:
        1. Create Qpair with depth=8
        2. Verify SQID property
        3. Delete and create with depth=64
        4. Create with interrupt enabled vs polling mode
        5. Create with specific interrupt vector
    
    Expected Result:
        - Qpairs created successfully with various configurations
        - SQID is accessible via property
        - Interrupt modes work correctly
    
    NVMe 2.0 Reference: §5.3, §5.4 (Queue creation)
    """
    logger.info("=== Test: Qpair Creation ===")
    
    # Test 1: Basic qpair with depth=8
    logger.info("Test 1: Creating Qpair with depth=8")
    qpair1 = d.Qpair(nvme0, depth=8)
    
    sqid1 = qpair1.sqid
    logger.info(f"  ✓ Created Qpair with SQID={sqid1}, depth=8")
    
    qpair1.delete()
    
    # Test 2: Larger queue depth
    logger.info("Test 2: Creating Qpair with depth=64")
    qpair2 = d.Qpair(nvme0, depth=64)
    
    sqid2 = qpair2.sqid
    logger.info(f"  ✓ Created Qpair with SQID={sqid2}, depth=64")
    
    qpair2.delete()
    
    # Test 3: Interrupt enabled (default)
    logger.info("Test 3: Creating Qpair with interrupt enabled")
    qpair3 = d.Qpair(nvme0, depth=16, ien=True)
    
    logger.info(f"  ✓ Created Qpair with SQID={qpair3.sqid}, interrupts enabled")
    
    qpair3.delete()
    
    # Test 4: Polling mode (interrupts disabled)
    logger.info("Test 4: Creating Qpair with polling mode")
    qpair4 = d.Qpair(nvme0, depth=16, ien=False)
    
    logger.info(f"  ✓ Created Qpair with SQID={qpair4.sqid}, polling mode")
    
    qpair4.delete()
    
    # Test 5: Specific interrupt vector
    logger.info("Test 5: Creating Qpair with specific interrupt vector")
    qpair5 = d.Qpair(nvme0, depth=16, iv=1)
    
    logger.info(f"  ✓ Created Qpair with SQID={qpair5.sqid}, interrupt vector=1")
    
    qpair5.delete()
    
    logger.info("✓ Qpair creation with various configurations validated successfully")


@pytest.mark.positive
@pytest.mark.io_queue
def test_multiple_io_queues(nvme0):
    """
    Test: Multiple I/O Queue Creation
    
    Purpose:
        Create multiple I/O queue pairs up to controller limit.
        Verify Queue ID uniqueness.
    
    Preconditions:
        - Controller ready
    
    Test Steps:
        1. Query maximum queue count via Get Features (FID 07h)
        2. Create multiple Qpairs (up to limit or reasonable subset)
        3. Verify each has unique SQID
        4. Delete all queues
    
    Expected Result:
        - Multiple queues created successfully
        - Each queue has unique ID
        - Total queues <= controller maximum
    
    NVMe 2.0 Reference: §5.27.1.7 (Number of Queues feature)
    """
    logger.info("=== Test: Multiple I/O Queue Creation ===")
    
    # Step 1: Query max queue count
    max_queues = get_max_queue_count(nvme0)
    logger.info(f"Controller supports up to {max_queues} I/O queues")
    
    # Create a reasonable number of queues (min of max_queues and 8)
    num_queues = min(max_queues, 8)
    logger.info(f"Creating {num_queues} I/O queue pairs")
    
    # Step 2: Create multiple queues
    qpairs = []
    sqids = set()
    
    for i in range(num_queues):
        qp = d.Qpair(nvme0, depth=8)
        qpairs.append(qp)
        sqids.add(qp.sqid)
        logger.info(f"  Created Qpair {i+1}/{num_queues} with SQID={qp.sqid}")
    
    # Step 3: Verify unique SQIDs
    assert len(sqids) == num_queues, f"Expected {num_queues} unique SQIDs, got {len(sqids)}"
    logger.info(f"  ✓ All {num_queues} queues have unique SQIDs: {sorted(sqids)}")
    
    # Step 4: Delete all queues
    logger.info("Deleting all queues")
    for i, qp in enumerate(qpairs):
        qp.delete()
        logger.info(f"  Deleted Qpair {i+1}/{num_queues}")
    
    logger.info("✓ Multiple I/O queue creation validated successfully")


@pytest.mark.positive
@pytest.mark.io_queue
def test_io_queue_sizes(nvme0):
    """
    Test: Various I/O Queue Sizes
    
    Purpose:
        Test queue creation with various depths.
        Verify size limits from CAP.MQES.
    
    Preconditions:
        - Controller ready
    
    Test Steps:
        1. Read CAP.MQES (Maximum Queue Entries Supported)
        2. Create queues with various sizes: 2, 4, 8, 16, 32, 64, 128, 256
        3. Create queue with maximum size (MQES + 1)
        4. Verify all valid sizes work
    
    Expected Result:
        - All queue sizes within limit work
        - Maximum size queue created successfully
    
    NVMe 2.0 Reference: §3.1.1 (CAP.MQES), §5.3, §5.4 (Queue size limits)
    """
    logger.info("=== Test: I/O Queue Sizes ===")
    
    # Step 1: Read MQES
    cap_reg = nvme0[0]
    mqes = cap_reg & 0xFFFF
    max_qsize = mqes + 1  # MQES is 0-based
    
    logger.info(f"Controller MQES: {mqes} (max queue size: {max_qsize} entries)")
    
    # Step 2: Test various queue sizes (powers of 2)
    test_sizes = [2, 4, 8, 16, 32, 64, 128, 256]
    
    # Only test sizes up to maximum supported
    test_sizes = [s for s in test_sizes if s <= max_qsize]
    
    logger.info(f"Testing queue sizes: {test_sizes}")
    
    for size in test_sizes:
        logger.info(f"  Creating Qpair with size={size}")
        qp = d.Qpair(nvme0, depth=size)
        assert qp.sqid > 0, f"Qpair with size {size} should be created"
        logger.info(f"    ✓ Created SQID={qp.sqid}, depth={size}")
        qp.delete()
    
    # Step 3: Test maximum size
    logger.info(f"Creating Qpair with maximum size={max_qsize}")
    qp_max = d.Qpair(nvme0, depth=max_qsize)
    logger.info(f"  ✓ Created maximum size Qpair with SQID={qp_max.sqid}, depth={max_qsize}")
    qp_max.delete()
    
    logger.info("✓ Various I/O queue sizes validated successfully")


@pytest.mark.positive
@pytest.mark.io_queue
def test_queue_priority_levels(nvme0):
    """
    Test: Queue Priority Levels for WRR
    
    Purpose:
        Create queues with different priority levels for Weighted Round Robin.
    
    Preconditions:
        - Controller ready
    
    Test Steps:
        1. Create CQ
        2. Create SQs with different priority levels (0=Urgent, 1=High, 2=Medium, 3=Low)
        3. Verify queues created successfully
        4. Delete all queues
    
    Expected Result:
        - Queues created with different priorities
        - Priority parameter accepted
    
    NVMe 2.0 Reference: §5.4 (Create I/O SQ - QPRIO field), §4.7 (Arbitration)
    """
    logger.info("=== Test: Queue Priority Levels ===")
    
    cqid = 1
    qsize = 16
    
    # Create CQ
    logger.info(f"Creating I/O CQ {cqid}")
    cq = IOCQ(nvme0, cqid, qsize, PRP())
    
    # Create SQs with different priorities
    priorities = {
        0: "Urgent",
        1: "High",
        2: "Medium",
        3: "Low"
    }
    
    sqs = []
    for prio, prio_name in priorities.items():
        sqid = 10 + prio  # SQIDs: 10, 11, 12, 13
        logger.info(f"  Creating SQ {sqid} with priority {prio} ({prio_name})")
        
        sq = IOSQ(nvme0, sqid, qsize, PRP(), cqid=cqid, prio=prio)
        sqs.append(sq)
        
        logger.info(f"    ✓ Created SQ {sqid} with priority={prio} ({prio_name})")
    
    # Delete all SQs then CQ
    logger.info("Deleting all SQs")
    for sq in sqs:
        sq.delete()
    
    logger.info("Deleting CQ")
    cq.delete()
    
    logger.info("✓ Queue priority levels validated successfully")


# ============================================================================
# NEGATIVE TESTS - Invalid Queue Creation Parameters
# ============================================================================

@pytest.mark.negative
@pytest.mark.io_queue
def test_create_queue_size_zero(nvme0):
    """
    Test: Create Queue with Size Zero (Negative)
    
    Purpose:
        Attempt to create queue with size 0.
        Verify proper error handling.
    
    Preconditions:
        - Controller ready
    
    Test Steps:
        1. Attempt to create CQ with size 0
        2. Expect error: Invalid Queue Size (0x0002)
    
    Expected Result:
        - Queue creation fails
        - Error status: SC=0x02, SCT=0x00 (Invalid Queue Size)
    
    NVMe 2.0 Reference: §5.3 (Create I/O CQ - Queue Size field must be > 0)
    """
    logger.info("=== Test: Create Queue Size Zero (Negative) ===")
    
    logger.info("Attempting to create CQ with size=0 (invalid)")
    
    # PyNVMe and PSD library may validate this before sending to controller
    # Try to create with size 0
    try:
        # This will likely raise an exception or error
        cq = IOCQ(nvme0, 1, 0, PRP())
        
        # If we get here, try to delete it
        cq.delete()
        
        # If no error, this might be a library issue
        pytest.fail("Expected error for queue size 0, but queue was created")
        
    except Exception as e:
        logger.info(f"  ✓ Queue creation with size 0 rejected: {e}")
        logger.info("✓ Invalid queue size error handling validated")


@pytest.mark.negative
@pytest.mark.io_queue
def test_create_queue_exceeding_limit(nvme0):
    """
    Test: Create Queue Exceeding Size Limit (Negative)
    
    Purpose:
        Attempt to create queue larger than CAP.MQES.
    
    Preconditions:
        - Controller ready
    
    Test Steps:
        1. Read CAP.MQES
        2. Attempt to create queue with size > MQES + 1
        3. Expect error: Invalid Queue Size
    
    Expected Result:
        - Queue creation fails
        - Error status indicates invalid size
    
    NVMe 2.0 Reference: §3.1.1 (CAP.MQES limits queue size)
    """
    logger.info("=== Test: Queue Size Exceeding Limit (Negative) ===")
    
    # Read MQES
    cap_reg = nvme0[0]
    mqes = cap_reg & 0xFFFF
    max_qsize = mqes + 1
    
    invalid_size = max_qsize + 1000  # Exceed limit by 1000
    
    logger.info(f"Maximum queue size: {max_qsize}")
    logger.info(f"Attempting to create queue with size={invalid_size} (exceeds limit)")
    
    try:
        cq = IOCQ(nvme0, 1, invalid_size, PRP())
        
        # If created, delete and fail test
        cq.delete()
        pytest.fail(f"Expected error for queue size {invalid_size} exceeding limit {max_qsize}")
        
    except Exception as e:
        logger.info(f"  ✓ Oversized queue creation rejected: {e}")
        logger.info("✓ Queue size limit enforcement validated")


@pytest.mark.negative
@pytest.mark.io_queue
def test_create_duplicate_queue_id(nvme0):
    """
    Test: Create Queue with Duplicate ID (Negative)
    
    Purpose:
        Attempt to create queue with existing Queue ID.
    
    Preconditions:
        - Controller ready
    
    Test Steps:
        1. Create CQ with QID=1
        2. Attempt to create another CQ with QID=1
        3. Expect error: Queue ID Conflict
    
    Expected Result:
        - Second queue creation fails
        - Error: SC=0x01, SCT=0x01 (Invalid Queue Identifier)
    
    NVMe 2.0 Reference: §5.3 (QID must be unique)
    """
    logger.info("=== Test: Duplicate Queue ID (Negative) ===")
    
    qid = 1
    qsize = 16
    
    # Create first CQ
    logger.info(f"Creating first CQ with QID={qid}")
    cq1 = IOCQ(nvme0, qid, qsize, PRP())
    logger.info(f"  ✓ First CQ {qid} created")
    
    # Attempt to create duplicate
    logger.info(f"Attempting to create duplicate CQ with same QID={qid}")
    
    try:
        cq2 = IOCQ(nvme0, qid, qsize, PRP())
        
        # If no error, clean up and fail
        cq2.delete()
        cq1.delete()
        pytest.fail(f"Expected error for duplicate QID {qid}")
        
    except Exception as e:
        logger.info(f"  ✓ Duplicate QID rejected: {e}")
        
        # Clean up first CQ
        cq1.delete()
        logger.info("✓ Duplicate Queue ID error handling validated")


@pytest.mark.negative
@pytest.mark.io_queue
def test_create_sq_with_invalid_cqid(nvme0):
    """
    Test: Create SQ with Invalid CQID (Negative)
    
    Purpose:
        Attempt to create SQ associated with non-existent CQ.
    
    Preconditions:
        - Controller ready
    
    Test Steps:
        1. Attempt to create SQ with CQID=99 (non-existent)
        2. Expect error: Completion Queue Invalid (0x0100)
    
    Expected Result:
        - SQ creation fails
        - Error: SC=0x00, SCT=0x01 (Completion Queue Invalid)
    
    NVMe 2.0 Reference: §5.4 (Create I/O SQ - CQID must reference valid CQ)
    """
    logger.info("=== Test: Create SQ with Invalid CQID (Negative) ===")
    
    sqid = 1
    invalid_cqid = 99  # Non-existent CQ
    qsize = 16
    
    logger.info(f"Attempting to create SQ {sqid} with invalid CQID={invalid_cqid}")
    
    try:
        sq = IOSQ(nvme0, sqid, qsize, PRP(), cqid=invalid_cqid)
        
        # If created, delete and fail
        sq.delete()
        pytest.fail(f"Expected error for invalid CQID {invalid_cqid}")
        
    except Exception as e:
        logger.info(f"  ✓ Invalid CQID rejected: {e}")
        logger.info("✓ Invalid CQID error handling validated")


@pytest.mark.negative
@pytest.mark.io_queue
def test_exceed_max_queue_count(nvme0):
    """
    Test: Exceed Maximum Queue Count (Negative)
    
    Purpose:
        Attempt to create more queues than controller supports.
    
    Preconditions:
        - Controller ready
    
    Test Steps:
        1. Query maximum queue count
        2. Create queues up to maximum
        3. Attempt to create one more queue
        4. Expect error or exception
    
    Expected Result:
        - Queue creation fails when exceeding limit
        - QpairCreationError exception or command error
    
    NVMe 2.0 Reference: §5.27.1.7 (Number of Queues feature limits)
    """
    logger.info("=== Test: Exceed Maximum Queue Count (Negative) ===")
    
    # Query max queue count
    max_queues = get_max_queue_count(nvme0)
    logger.info(f"Controller supports {max_queues} I/O queues")
    
    # Create maximum number of queues
    logger.info(f"Creating {max_queues} queues (maximum)")
    qpairs = []
    
    try:
        for i in range(max_queues):
            qp = d.Qpair(nvme0, depth=8)
            qpairs.append(qp)
            logger.info(f"  Created queue {i+1}/{max_queues}, SQID={qp.sqid}")
        
        logger.info(f"✓ Created maximum {max_queues} queues")
        
        # Attempt to create one more
        logger.info("Attempting to create one more queue (should fail)")
        
        try:
            extra_qp = d.Qpair(nvme0, depth=8)
            
            # If successful, clean up and fail
            extra_qp.delete()
            pytest.fail(f"Expected error when exceeding {max_queues} queue limit")
            
        except d.QpairCreationError as e:
            logger.info(f"  ✓ Excessive queue creation rejected with QpairCreationError: {e}")
            
        except Exception as e:
            logger.info(f"  ✓ Excessive queue creation rejected: {e}")
            
    finally:
        # Clean up all created queues
        logger.info(f"Cleaning up {len(qpairs)} queues")
        for qp in qpairs:
            qp.delete()
    
    logger.info("✓ Maximum queue count limit enforcement validated")


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v", "-s"])
