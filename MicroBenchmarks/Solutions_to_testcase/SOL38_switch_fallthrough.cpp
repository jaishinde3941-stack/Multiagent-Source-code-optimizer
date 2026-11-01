// Category: Control Flow Errors (Success Case)
// Expected Result: Use break statements appropriately in switch

#include <iostream>

int main() {
    int choice = 1;
    
    switch (choice) {
        case 1:
            std::cout << "Choice 1" << std::endl;
            break;  // SUCCESS: Added break to prevent fallthrough
        case 2:
            std::cout << "Choice 2" << std::endl;
            break;
        case 3:
            std::cout << "Choice 3" << std::endl;
            break;
        default:
            std::cout << "Default" << std::endl;
    }
    
    return 0;
}
